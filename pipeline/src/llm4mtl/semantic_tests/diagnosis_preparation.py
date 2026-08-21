"""Prepare Source Diagnosis evidence, and only after Stage 11 has failed.

The order matters more than anything else in this module. A generated test earns
the right to say something about a generated transformation by first passing on
the *reference* transformation; only then does it run against the generated one,
and only a failure of that last run is a semantic failure worth diagnosing. So
this module reads exactly one thing: an immutable ``execution`` stage attempt.
It never looks at extraction, technical, or reference results to decide *whether*
to build a report — those decide whether the pair was allowed to execute at all,
and the execution stage already refuses pairs whose suite is not reference-valid.

What it assembles, per failing pair, is one report per recorded assertion
failure, from six sources:

* the generated transformation and its hash — from the pair's observation;
* the parser verdict for that transformation — from the syntax-validation
  attempt of the same run;
* the generated test — from the immutable candidate directory the observation
  names, narrowed to the one semantic case that failed;
* the same test's reference history — from the reference observation of this run;
* what failed on the generated transformation — from the pair's observation;
* the raw failure — from the execution evidence archived beside it.

Nothing here classifies a failure, calls an LLM, or writes a stage result. The
mapping from a Surefire method back to a semantic case is the renderer's own
name function run forwards over every case, so a report is attached to a case
only when exactly one case could have produced that method.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from xml.etree import ElementTree as ET

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.paths import REPO_ROOT
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_method_name
from llm4mtl.semantic_tests.execution_evidence import archived_execution_evidence
from llm4mtl.semantic_tests.failure_report import (
    FailureReportError,
    PairReportRequest,
    ReportRequest,
    write_failure_report,
    write_pair_failure_report,
)
from llm4mtl.serialization.json_io import read_json, write_json_once

SCHEMA_VERSION = "1.0"
INDEX_FILENAME = "index.json"
REPORTS_DIRNAME = "reports"
RESPONSES_DIRNAME = "responses"
SOURCE_DIAGNOSIS_DIRNAME = "source-diagnosis"
EXECUTION_STAGE = "execution"
SYNTAX_STAGE = "syntax-validation"
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class DiagnosisPreparationError(RuntimeError):
    """Raised when the requested execution attempt cannot be read at all."""


@dataclass(frozen=True)
class IndexedFailureReport:
    """One schema-validated report referenced by a diagnosis index."""

    reference: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SurefireFailure:
    """One recorded failure, exactly as the archived report has it.

    ``kind`` keeps the two JUnit outcomes apart: ``assertion_failure`` is a
    check that was evaluated and lost, ``runtime_error`` is a throw before any
    verdict. Both are real failures of the pairing and both are diagnosed; only
    the first can name an assertion.
    """

    report: Path
    kind: str
    test_class: str
    test_method: str
    message: str


def prepare_after_execution_stage(
    run_dir: Path,
    stage: str,
    payload: dict[str, Any],
    attempt: int,
) -> dict[str, Any] | None:
    """Assemble diagnosis evidence when — and only when — Stage 11 failed.

    Called by both stage entry points right after the execution attempt has been
    recorded. It reads that attempt and writes nothing else: preparation is
    deterministic post-processing, so it must never change the stage result, the
    run status, or the events timeline. A failure to assemble evidence is
    likewise not a stage failure; it is recorded in the index and the caller
    continues.
    """
    if stage != EXECUTION_STAGE:
        return None
    # `failed` counts the pairs whose reference-validated suite lost on a
    # generated transformation. Anything else — passed, skipped, an
    # infrastructure error — is not a semantic failure to diagnose.
    if int(payload.get("counts", {}).get("failed", 0)) <= 0:
        return None
    try:
        return prepare_execution_diagnosis(Path(run_dir), attempt)
    except (DiagnosisPreparationError, OSError, ValueError) as exc:
        # The stage keeps its verdict, but the run must still say that its
        # evidence could not be assembled. A silently absent diagnosis directory
        # is indistinguishable from a run that had nothing to diagnose.
        return _record_preparation_error(Path(run_dir), attempt, exc)


def diagnosis_artifact_references(
    run_dir: Path, index: dict[str, Any] | None
) -> dict[str, str]:
    """Pointers into the prepared evidence, for the caller that must route on it.

    Preparation writes the reports; naming which one a diagnosis should read is
    a separate question, and it is answered here rather than by the workflow
    that consumes the stage result. Python already knows which report is
    diagnosable, so making n8n re-derive that from the filesystem would put the
    same rule in two places and let them disagree.

    ``failure_report_index`` always accompanies a prepared attempt, so a caller
    that wants every report can read them all. ``failure_report_path`` is added
    when a report was created and the report itself declares the pair
    diagnosable. A missing key is a fact — there is nothing to diagnose — and is
    deliberately not an empty string.

    Eligibility already requires a syntactically valid transformation, a suite
    that passed on the reference, and at least one observed fact about the
    failure. It deliberately does not require the model-level comparator
    difference: no comparator produces one yet, so demanding it here would
    reject every real report and leave the observed evidence — the JUnit
    expected/actual pair, the target-model snapshots, the recorded exception —
    unused.
    """
    if not index:
        return {}
    attempt = index.get("attempt")
    if not isinstance(attempt, int):
        return {}
    paths = RunPaths(root=Path(run_dir).resolve())
    references = {
        "failure_report_index": _repository_path(
            _diagnosis_dir(paths, attempt) / INDEX_FILENAME
        )
    }
    selected = _first_diagnosable_report(index)
    if selected is not None:
        references["failure_report_path"] = selected
    return references


def read_diagnosis_queue(run_dir: Path, attempt: int) -> dict[str, Any]:
    """Read, validate, and normalize the diagnosable reports for resume/routing."""
    paths = RunPaths(root=Path(run_dir).resolve())
    index_path, index = _read_diagnosis_index(paths, attempt)
    eligible_reports: list[dict[str, Any]] = []
    for pair in index["pairs"]:
        for report in pair["reports"]:
            if not _is_diagnosable_report(report):
                continue
            _read_indexed_failure_report(paths, attempt, report)
            eligible_reports.append(
                {
                    "failure_report_path": report["report"],
                    "scope": report.get("scope", "test_case"),
                    "test_case_id": report.get("test_case_id"),
                    "assertion_id": report.get("assertion_id"),
                }
            )
    return {
        "run_id": paths.root.name,
        "attempt": attempt,
        "counts": index["counts"],
        "eligible_reports": eligible_reports,
        "failure_report_index": _repository_path(index_path),
    }


def read_failure_reports_for_attempt(
    run_dir: Path, attempt: int
) -> list[IndexedFailureReport]:
    """Return only reports referenced by one execution attempt's validated index."""
    paths = RunPaths(root=Path(run_dir).resolve())
    _, index = _read_diagnosis_index(paths, attempt)
    reports: list[IndexedFailureReport] = []
    for pair in index["pairs"]:
        for entry in pair["reports"]:
            if not isinstance(entry, dict) or entry.get("status") != "created":
                continue
            reports.append(_read_indexed_failure_report(paths, attempt, entry))
    return reports


def _read_diagnosis_index(
    paths: RunPaths, attempt: int
) -> tuple[Path, dict[str, Any]]:
    index_path = _diagnosis_dir(paths, attempt) / INDEX_FILENAME
    if not index_path.is_file():
        raise DiagnosisPreparationError(
            f"no diagnosis index for execution attempt {attempt}"
        )
    index = read_json(index_path)
    validate_artifact("diagnosis-index", index)
    if index.get("run_id") != paths.root.name or index.get("attempt") != attempt:
        raise DiagnosisPreparationError("diagnosis index identity does not match request")
    return index_path, index


def _read_indexed_failure_report(
    paths: RunPaths, attempt: int, entry: dict[str, Any]
) -> IndexedFailureReport:
    reference = entry.get("report")
    if not isinstance(reference, str) or not reference:
        raise DiagnosisPreparationError("created diagnosis report has no file reference")
    candidate = Path(reference)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    expected_directory = (
        _diagnosis_dir(paths, attempt) / REPORTS_DIRNAME
    ).resolve()
    try:
        relative = resolved.relative_to(expected_directory)
    except ValueError as exc:
        raise DiagnosisPreparationError(
            f"diagnosis report is outside run {paths.root.name} attempt {attempt}: "
            f"{reference}"
        ) from exc
    if len(relative.parts) != 1:
        raise DiagnosisPreparationError(
            f"diagnosis report is not a direct attempt report: {reference}"
        )
    if not resolved.is_file():
        raise DiagnosisPreparationError(f"diagnosis report is missing: {reference}")
    try:
        report = read_json(resolved)
        validate_artifact("failure-report", report)
    except (OSError, ValueError) as exc:
        raise DiagnosisPreparationError(
            f"diagnosis report is invalid: {reference}: {exc}"
        ) from exc
    identity = report.get("identity")
    if not isinstance(identity, dict):
        raise DiagnosisPreparationError(
            f"diagnosis report has no identity: {reference}"
        )
    if identity.get("run_id") != paths.root.name or identity.get("attempt") != attempt:
        raise DiagnosisPreparationError(
            f"diagnosis report identity does not match run/attempt: {reference}"
        )
    return IndexedFailureReport(reference=reference, payload=report)


def _first_diagnosable_report(index: dict[str, Any]) -> str | None:
    """The first report a diagnosis can actually be asked to read.

    Order is the recorded one — pairs as the execution evidence listed them,
    reports as Surefire reported the failures — so the same attempt always
    selects the same report.
    """
    pairs = index.get("pairs")
    if not isinstance(pairs, list):
        return None
    for pair in pairs:
        reference = _first_diagnosable_pair_report(pair)
        if reference is not None:
            return reference
    return None


def _first_diagnosable_pair_report(pair: object) -> str | None:
    """Return the first usable report reference recorded for one pair."""
    if not isinstance(pair, dict):
        return None
    reports = pair.get("reports")
    if not isinstance(reports, list):
        return None
    for report in reports:
        if not _is_diagnosable_report(report):
            continue
        reference = report.get("report")
        if isinstance(reference, str):
            return reference
    return None


def _is_diagnosable_report(report: object) -> bool:
    """Return whether an index entry names a created, eligible report."""
    return (
        isinstance(report, dict)
        and report.get("status") == "created"
        and report.get("eligible") is True
    )


def _record_preparation_error(
    run_dir: Path, attempt: int, error: Exception
) -> dict[str, Any] | None:
    index = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "stage": EXECUTION_STAGE,
        "attempt": attempt,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "execution_evidence": None,
        "syntax_evidence": None,
        "error": f"{type(error).__name__}: {error}",
        "counts": _index_counts([]),
        "pairs": [],
    }
    try:
        validate_artifact("diagnosis-index", index)
        write_json_once(
            _diagnosis_dir(RunPaths(root=run_dir.resolve()), attempt) / INDEX_FILENAME,
            index,
        )
    except OSError:
        return None
    return index


def prepare_execution_diagnosis(run_dir: Path, attempt: int) -> dict[str, Any]:
    """Build every failure report the given execution attempt justifies.

    Returns the index, whether or not any report could be created. The index is
    written once per attempt: a second call returns the existing one instead of
    re-deriving evidence that is already immutable.
    """
    paths = RunPaths(root=Path(run_dir).resolve())
    index_path = _diagnosis_dir(paths, attempt) / INDEX_FILENAME
    if index_path.is_file():
        existing = read_json(index_path)
        validate_artifact("diagnosis-index", existing)
        # Idempotent: a re-read must still leave the trace directory in place,
        # so a run whose evidence was prepared before this existed can be
        # diagnosed without re-deriving it.
        _ensure_diagnosis_response_dir(paths, attempt, existing)
        return existing

    evidence_path = paths.stage_attempt_evidence(EXECUTION_STAGE, attempt)
    if not evidence_path.is_file():
        raise DiagnosisPreparationError(
            f"no execution attempt {attempt} recorded under {paths.root}"
        )
    evidence = read_json(evidence_path)
    syntax_evidence = _latest_syntax_evidence(paths)

    pairs = [
        _prepare_pair(
            paths=paths,
            attempt=attempt,
            pair=pair,
            execution_evidence=evidence_path,
            syntax_evidence=syntax_evidence,
        )
        for pair in _failed_pairs(evidence)
    ]

    index = {
        "schema_version": SCHEMA_VERSION,
        "run_id": paths.root.name,
        "stage": EXECUTION_STAGE,
        "attempt": attempt,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "execution_evidence": _repository_path(evidence_path),
        "syntax_evidence": (
            _repository_path(syntax_evidence) if syntax_evidence is not None else None
        ),
        "counts": _index_counts(pairs),
        "pairs": pairs,
    }
    validate_artifact("diagnosis-index", index)
    _ensure_diagnosis_response_dir(paths, attempt, index)
    write_json_once(index_path, index)
    return index


def diagnosis_response_dir(run_dir: Path, attempt: int) -> Path:
    """Where a diagnosis of this execution attempt records what it was asked.

    The trace a diagnosis leaves — the exact request, the raw answer, the
    validated verdict — belongs to the attempt that produced the evidence, so it
    is grouped by attempt and named by the n8n execution that wrote it. The
    directory is prepared here rather than by the workflow because the node that
    writes a file cannot create the path to it, and shelling out to `mkdir` ties
    the workflow to a node that a default n8n container does not ship.
    """
    return (
        Path(run_dir)
        / RESPONSES_DIRNAME
        / SOURCE_DIAGNOSIS_DIRNAME
        / f"execution-attempt-{attempt:03d}"
    )


def _ensure_diagnosis_response_dir(
    paths: RunPaths, attempt: int, index: dict[str, Any]
) -> None:
    """Create the trace directory only for an attempt that can be diagnosed.

    An attempt with nothing diagnosable gets no directory: an empty one would
    claim a diagnosis was possible and none was.
    """
    if int(index.get("counts", {}).get("diagnosis_eligible", 0)) <= 0:
        return
    try:
        diagnosis_response_dir(paths.root, attempt).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DiagnosisPreparationError(
            f"cannot prepare diagnosis response directory for execution "
            f"attempt {attempt:03d}: {exc}"
        ) from exc


def _failed_pairs(evidence: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """The recorded pairs whose assertions did not pass.

    A pair that passed is not a failure, and a pair the stage could not run is
    not one either — but the difference between "threw" and "disagreed" is a
    fact of the observation, so both are yielded and separated per pair below.
    """
    pairs = evidence.get("details", {}).get("pairs")
    if not isinstance(pairs, list):
        return
    for pair in pairs:
        if isinstance(pair, dict) and pair.get("assertions_passed") is False:
            yield pair


def _prepare_pair(
    *,
    paths: RunPaths,
    attempt: int,
    pair: dict[str, Any],
    execution_evidence: Path,
    syntax_evidence: Path | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "suite": pair.get("suite"),
        "transformation": pair.get("transformation"),
        "observation": pair.get("evidence"),
        "failure_stage": pair.get("failure_stage"),
        "reports": [],
        "skipped": [],
    }
    observation_path = _optional_path(pair.get("evidence"))
    if observation_path is None or not observation_path.is_file():
        entry["skipped"].append(
            _skip("no_recorded_observation", str(pair.get("evidence")))
        )
        return entry
    if syntax_evidence is None:
        entry["skipped"].append(
            _skip(
                "no_syntax_validation_attempt",
                "the run recorded no syntax-validation attempt to read the parser "
                "verdict for this transformation from",
            )
        )
        return entry

    execution = read_json(observation_path)
    suite_dir = _optional_path(
        execution.get("inputs", {}).get("suite", {}).get("path")
    )
    if suite_dir is None or not suite_dir.is_dir():
        entry["skipped"].append(_skip("no_candidate_suite_directory", str(suite_dir)))
        return entry

    archived = archived_execution_evidence(observation_path)
    if archived.directory is None:
        entry["skipped"].append(
            _skip(
                "no_archived_execution_evidence",
                "the execution kept no Maven output or Surefire report, so the "
                "failure cannot be attributed to a concrete assertion",
            )
        )
        return entry

    reference_execution = _reference_observation(paths, execution)
    failures = _recorded_failures(archived.surefire_reports)
    if not failures:
        # No per-test entry at all: the run failed before Surefire could
        # attribute anything to a test method (a transformation the engine
        # refused, a harness that died during setup). The failure is no less
        # real, and the evidence the run preserved still describes it — so the
        # pair itself becomes the subject of the report, with no case and no
        # assertion invented to fill the per-case shape.
        entry["reports"].append(
            _prepare_pair_report(
                paths=paths,
                attempt=attempt,
                execution=execution,
                observation_path=observation_path,
                execution_evidence=execution_evidence,
                syntax_evidence=syntax_evidence,
                reference_execution=reference_execution,
            )
        )
        return entry

    semantic_cases = _read_semantic_cases(suite_dir)
    if semantic_cases is None:
        entry["skipped"].append(_skip("no_semantic_cases", str(suite_dir)))
        return entry

    for failure in failures:
        entry["reports"].append(
            _prepare_report(
                paths=paths,
                attempt=attempt,
                failure=failure,
                execution=execution,
                observation_path=observation_path,
                suite_dir=suite_dir,
                semantic_cases=semantic_cases,
                execution_evidence=execution_evidence,
                syntax_evidence=syntax_evidence,
                reference_execution=reference_execution,
            )
        )
    return entry


def _prepare_report(
    *,
    paths: RunPaths,
    attempt: int,
    failure: SurefireFailure,
    execution: dict[str, Any],
    observation_path: Path,
    suite_dir: Path,
    semantic_cases: dict[str, Any],
    execution_evidence: Path,
    syntax_evidence: Path,
    reference_execution: Path | None,
) -> dict[str, Any]:
    """One report for one recorded assertion failure, or why there is none."""
    try:
        test_case_id = _match_test_case(semantic_cases, failure.test_method)
        # A throw lost no assertion, so none is named. Naming one would
        # attribute the failure to a check that never ran.
        assertion_id = (
            _match_assertion(semantic_cases, test_case_id, failure.message)
            if failure.kind == "assertion_failure"
            else None
        )
    except FailureReportError as exc:
        return {
            "status": "refused",
            "test_method": failure.test_method,
            "detail": str(exc),
        }

    payload = {
        "run_manifest": _repository_path(paths.manifest),
        "syntax_evidence": _repository_path(syntax_evidence),
        "execution_evidence": _repository_path(execution_evidence),
        "generated_execution": _repository_path(observation_path),
        "reference_execution": (
            _repository_path(reference_execution)
            if reference_execution is not None
            else None
        ),
        "test_case_id": test_case_id,
        "assertion_id": assertion_id,
        "attempt": attempt,
        "actual_target_models": [
            _repository_path(path)
            for path in _actual_target_models(observation_path, failure.test_method)
        ],
        # Surefire reports and the Maven log are resolved from the archive the
        # execution wrote beside this observation. Naming the workspace copies
        # would name files the next `mvn clean` has already deleted.
        "actual_vs_expected": None,
    }
    output = _report_path(paths, attempt, execution, test_case_id, assertion_id)
    try:
        request = ReportRequest.from_payload(payload)
        report = write_failure_report(request, output)
    except FailureReportError as exc:
        return {
            "status": "refused",
            "test_method": failure.test_method,
            "test_case_id": test_case_id,
            "assertion_id": assertion_id,
            "detail": str(exc),
        }
    diagnosis = report["source_diagnosis"]
    return {
        "status": "created",
        "test_method": failure.test_method,
        "test_case_id": test_case_id,
        "assertion_id": assertion_id,
        "report": _repository_path(output),
        "eligible": diagnosis["eligible"],
        "reason": diagnosis["reason"],
    }


def _prepare_pair_report(
    *,
    paths: RunPaths,
    attempt: int,
    execution: dict[str, Any],
    observation_path: Path,
    execution_evidence: Path,
    syntax_evidence: Path,
    reference_execution: Path | None,
) -> dict[str, Any]:
    """One report about the execution pair itself, or why there is none."""
    payload = {
        "run_manifest": _repository_path(paths.manifest),
        "syntax_evidence": _repository_path(syntax_evidence),
        "execution_evidence": _repository_path(execution_evidence),
        "generated_execution": _repository_path(observation_path),
        "reference_execution": (
            _repository_path(reference_execution)
            if reference_execution is not None
            else None
        ),
        "attempt": attempt,
    }
    output = _pair_report_path(paths, attempt, execution)
    try:
        request = PairReportRequest.from_payload(payload)
        report = write_pair_failure_report(request, output)
    except FailureReportError as exc:
        return {
            "status": "refused",
            "scope": "execution_pair",
            "detail": str(exc),
        }
    diagnosis = report["source_diagnosis"]
    return {
        "status": "created",
        "scope": "execution_pair",
        # Explicitly null, so a reader of the index sees that this failure was
        # attributed to no case rather than that the fields went missing.
        "test_case_id": None,
        "assertion_id": None,
        "report": _repository_path(output),
        "eligible": diagnosis["eligible"],
        "reason": diagnosis["reason"],
    }


def _recorded_failures(reports: tuple[Path, ...]) -> list[SurefireFailure]:
    """Every ``<failure>`` and ``<error>`` in the archived reports, in order.

    Errors are included because a validated test that throws on a generated
    transformation has failed against it, and attributing that failure is what
    Source Diagnosis is for. An error is checked first: a case that both threw
    and lost an assertion never reached a trustworthy verdict, so the throw is
    what the report is about.
    """
    failures: list[SurefireFailure] = []
    for path in reports:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            # A report that cannot be parsed is not evidence of a failure. The
            # file itself stays archived; nothing is inferred from its absence.
            continue
        for case in root.iter("testcase"):
            failure = _recorded_failure(path, case)
            if failure is not None:
                failures.append(failure)
    return failures


def _recorded_failure(path: Path, case: ET.Element) -> SurefireFailure | None:
    error = case.find("error")
    node = error if error is not None else case.find("failure")
    if node is None:
        return None
    return SurefireFailure(
        report=path,
        kind="runtime_error" if error is not None else "assertion_failure",
        test_class=str(case.get("classname") or ""),
        test_method=str(case.get("name") or ""),
        message=str(node.get("message") or ""),
    )


def _match_test_case(semantic_cases: dict[str, Any], test_method: str) -> str:
    """The one semantic case whose rendered method name is ``test_method``."""
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise FailureReportError("semantic_cases.json has no tests array")
    matching = [
        identifier
        for test in tests
        if isinstance(test, dict)
        for identifier in [str(test.get("id") or test.get("name") or "")]
        if identifier and sanitize_method_name(identifier) == test_method
    ]
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one semantic case rendering to {test_method!r}, "
            f"found {len(matching)}"
        )
    return matching[0]


def _match_assertion(
    semantic_cases: dict[str, Any], test_case_id: str, message: str
) -> str:
    """The assertion id whose rendered message the failure message starts with.

    The harness prints the assertion's own message and may append its own detail
    (``... missing X``, ``... ==> expected: <1> but was: <0>``), so the recorded
    message is matched as a prefix. Two assertions that render the same message
    are indistinguishable in the report, and the failure is refused rather than
    attributed to whichever came first.
    """
    tests = semantic_cases.get("tests")
    test_case = next(
        (
            test
            for test in tests
            if isinstance(test, dict)
            and str(test.get("id") or test.get("name") or "") == test_case_id
        ),
        None,
    )
    if test_case is None:
        raise FailureReportError(f"semantic case {test_case_id!r} disappeared")
    assertions = test_case.get("assertions")
    if not isinstance(assertions, list):
        raise FailureReportError(f"semantic case {test_case_id!r} has no assertions")

    matching = _matching_assertion_ids(assertions, message.strip())
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one assertion of {test_case_id!r} matching the "
            f"recorded failure message, found {len(matching)}"
        )
    return matching[0]


def _matching_assertion_ids(
    assertions: list[Any], stripped_message: str
) -> list[str]:
    """Return assertion IDs whose rendered messages match the recorded prefix."""
    matching: list[str] = []
    for index, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        rendered = _rendered_assertion_message(assertion)
        if rendered and stripped_message.startswith(rendered):
            matching.append(str(assertion.get("id") or f"assertion-{index:03d}"))
    return matching


def _rendered_assertion_message(assertion: dict[str, Any]) -> str:
    """The message the Java renderer emits for ``assertion``.

    Kept identical to ``llm4mtl.languages.java_assertions``: this function reads
    a value back out of a Surefire report, so any divergence would silently stop
    matching real failures.
    """
    explicit = assertion.get("message")
    if isinstance(explicit, str) and explicit:
        return explicit
    if not all(field in assertion for field in ("kind", "model", "type")):
        return ""
    return (
        f"{assertion['kind']} assertion for "
        f"{assertion['model']}::{assertion['type']}"
    )


def _actual_target_models(observation_path: Path, test_method: str) -> list[Path]:
    """The actual output models this execution wrote for this test case.

    They live beside the observation, under ``snapshots/<test-method>/``, so a
    snapshot is identified by the transformation, the suite, the case, and the
    model slot together. Reading them from a directory shared by every suite of
    one transformation is what would let a diagnosis cite another suite's
    output as this failure's actual result.
    """
    directory = observation_path.parent / "snapshots" / test_method
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.xmi") if path.is_file())


def _reference_observation(paths: RunPaths, execution: dict[str, Any]) -> Path | None:
    """This run's reference observation for the same suite, when it recorded one."""
    try:
        candidate = (
            paths.root
            / "observations"
            / str(execution["task"])
            / str(execution["llm"])
            / str(execution["strategy"])
            / str(execution["suite_id"])
            / "suite_execution.json"
        )
    except KeyError:
        return None
    return candidate if candidate.is_file() else None


def _read_semantic_cases(suite_dir: Path) -> dict[str, Any] | None:
    path = suite_dir / "semantic_cases.json"
    if not path.is_file():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _latest_syntax_evidence(paths: RunPaths) -> Path | None:
    attempts = paths.stage_attempts_dir(SYNTAX_STAGE)
    if not attempts.is_dir():
        return None
    for attempt in sorted(existing_attempts(attempts), reverse=True):
        evidence = paths.stage_attempt_evidence(SYNTAX_STAGE, attempt)
        if evidence.is_file():
            return evidence
    return None


def _diagnosis_dir(paths: RunPaths, attempt: int) -> Path:
    return paths.root / "diagnosis" / EXECUTION_STAGE / f"attempt-{attempt:03d}"


def _pair_report_path(
    paths: RunPaths, attempt: int, execution: dict[str, Any]
) -> Path:
    name = "__".join(
        _safe(part)
        for part in (
            _transformation_hash(execution)[:12] or "transformation",
            str(execution.get("suite_id", "suite")),
            "execution-pair",
        )
    )
    return _diagnosis_dir(paths, attempt) / REPORTS_DIRNAME / f"{name}.json"


def _transformation_hash(execution: dict[str, Any]) -> str:
    return str(execution.get("inputs", {}).get("transformation", {}).get("sha256", ""))


def _report_path(
    paths: RunPaths,
    attempt: int,
    execution: dict[str, Any],
    test_case_id: str,
    assertion_id: str,
) -> Path:
    # The transformation hash is part of the name because one attempt can pair
    # the same suite with several generated transformations, and two reports
    # about different transformations are different evidence.
    transformation_hash = _transformation_hash(execution)
    name = "__".join(
        _safe(part)
        for part in (
            transformation_hash[:12] or "transformation",
            str(execution.get("suite_id", "suite")),
            test_case_id,
            # A throw names no assertion, and the name says so rather than
            # borrowing an assertion id that was never reached.
            assertion_id or "runtime-error",
        )
    )
    return _diagnosis_dir(paths, attempt) / REPORTS_DIRNAME / f"{name}.json"


def _index_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
    """Counts about the prepared evidence only.

    None of these is a metric about the experiment. The stage's own counts —
    what passed, what failed, what was evaluated — were written before
    preparation ran and are never touched by it, so a report that comes into
    existence here cannot move a semantic result.
    """
    reports = [report for pair in pairs for report in pair["reports"]]
    report_counts = _prepared_report_counts(reports)
    return {
        "failed_pairs": len(pairs),
        "reports_created": report_counts["reports_created"],
        "reports_refused": report_counts["reports_refused"],
        "pair_level_reports": report_counts["pair_level_reports"],
        "diagnosis_eligible": report_counts["diagnosis_eligible"],
        "pairs_without_reports": sum(1 for pair in pairs if not pair["reports"]),
    }


def _prepared_report_counts(reports: list[dict[str, Any]]) -> dict[str, int]:
    created: list[dict[str, Any]] = []
    refused_count = 0
    eligible_count = 0
    for report in reports:
        if report["status"] == "created":
            created.append(report)
        elif report["status"] == "refused":
            refused_count += 1
        if report.get("eligible"):
            eligible_count += 1

    return {
        "reports_created": len(created),
        "reports_refused": refused_count,
        "pair_level_reports": sum(
            1 for report in created if report.get("scope") == "execution_pair"
        ),
        "diagnosis_eligible": eligible_count,
    }


def _skip(reason: str, detail: str) -> dict[str, str]:
    return {"reason": reason, "detail": detail}


def _safe(value: str) -> str:
    cleaned = SAFE_NAME.sub("-", value).strip("-")
    return cleaned or "unnamed"


def _optional_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def _repository_path(path: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)
