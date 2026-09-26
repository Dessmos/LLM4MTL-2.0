"""Prepare Source Diagnosis evidence, only after the execution stage has failed.

Order matters most here. A generated test may judge a generated transformation
only after it passed on the *reference* transformation. Only a failure of the
later run, against the generated transformation, is a semantic failure worth
diagnosing. So this module reads exactly one thing: an immutable ``execution``
stage attempt. It never reads extraction, technical, or reference results to
decide *whether* to build a report. Those decided whether the pair could run at
all, and the execution stage only runs reference-valid suites.

For each failing pair it writes one report per recorded test-method failure (a
lost assertion or a runtime throw), or one pair-level report when no test method
was reached. The sources are:

* the generated transformation and its hash — from the pair's observation;
* the parser verdict for that transformation — from the syntax-validation
  attempt of the same run;
* the generated test — from the immutable candidate directory the observation
  names, narrowed to the failing semantic case when it is known;
* the same test's reference result — from this run's reference observation;
* what failed on the generated transformation — from the pair's observation;
* the raw failure — from the execution evidence archived beside it.

Nothing here classifies a failure, calls an LLM, or writes a stage result. A
Surefire method is mapped back to a semantic case by rendering every case name
the way the renderers do. A report names a case only when exactly one case could
have produced that method.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from xml.etree import ElementTree as ET

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.domain.observations import FailureStage
from llm4mtl.paths import REPO_ROOT, repository_relative
from llm4mtl.run_store.attempts import attempt_dir_name, existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.semantic_tests.codegen.java_rendering import assertion_message
from llm4mtl.semantic_tests.execution_evidence import archived_execution_evidence
from llm4mtl.semantic_tests.failure_report import (
    ASSERTION_FAILURE_KIND,
    CASE_SCOPE,
    FAILURE_REPORT_SCHEMA,
    PAIR_SCOPE,
    RUNTIME_ERROR_KIND,
    FailureReportError,
    assertion_id,
    case_id,
    rendered_method_name,
    write_report,
)
from llm4mtl.semantic_tests.semantic_spec import SEMANTIC_CASES_FILE
from llm4mtl.semantic_tests.suite_execution import (
    OBSERVATION_FILENAME,
    SNAPSHOTS_DIRNAME,
)
from llm4mtl.semantic_tests.surefire import testcase_method_name, testcase_outcome
from llm4mtl.serialization.json_io import read_json, write_json_once
from llm4mtl.vocabulary import EXECUTION_STAGE_ID, SYNTAX_VALIDATION_STAGE_ID

SCHEMA_VERSION = "1.0"
DIAGNOSIS_INDEX_SCHEMA = "diagnosis-index"
DIAGNOSIS_DIRNAME = "diagnosis"
INDEX_FILENAME = "index.json"
REPORTS_DIRNAME = "reports"
SOURCE_DIAGNOSIS_DIRNAME = "source-diagnosis"
SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
# The ``status`` of one report entry in the index.
REPORT_CREATED = "created"
REPORT_REFUSED = "refused"
# How many leading characters of the transformation hash a report file name uses.
REPORT_NAME_HASH_CHARS = 12


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

    kind: str
    test_method: str
    message: str


@dataclass(frozen=True)
class _PairEvidence:
    """What one failed pair recorded, located once for all of its reports."""

    paths: RunPaths
    attempt: int
    failure_stage: Any
    execution: dict[str, Any]
    observation_path: Path
    suite_dir: Path
    execution_evidence: Path
    syntax_evidence: Path
    reference_execution: Path | None
    surefire_reports: tuple[Path, ...]


class _PairSkipped(Exception):
    """A failed pair that gets no report, and the recorded reason why."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.skip = {"reason": reason, "detail": detail}


def prepare_after_execution_stage(
    run_dir: Path,
    stage: str,
    payload: dict[str, Any],
    attempt: int,
) -> dict[str, Any] | None:
    """Assemble diagnosis evidence only when the execution stage failed.

    Called through :func:`llm4mtl.stage_recording.record_stage_attempt` right
    after the execution attempt is recorded. It
    writes only diagnosis files and must never change the stage result, the run
    status, or the events. A failure to assemble evidence is not a stage
    failure: it is recorded in the index and the caller continues.

    Returns the diagnosis index, or ``None`` when there is nothing to diagnose
    or even the error index could not be written.
    """
    if stage != EXECUTION_STAGE_ID:
        return None
    # `failed` counts the pairs whose reference-validated suite failed on a
    # generated transformation. Passed, skipped, or infrastructure-error pairs
    # are not semantic failures.
    if int(payload.get("counts", {}).get("failed", 0)) <= 0:
        return None
    try:
        return prepare_execution_diagnosis(Path(run_dir), attempt)
    except (DiagnosisPreparationError, OSError, ValueError) as exc:
        # The stage keeps its verdict, but the run must record that its evidence
        # could not be assembled. A missing index would look like a run with
        # nothing to diagnose.
        return _record_preparation_error(Path(run_dir), attempt, exc)


def diagnosis_artifact_references(
    run_dir: Path, index: dict[str, Any] | None
) -> dict[str, str]:
    """Pointers into the prepared evidence, for the caller that routes on it.

    Python already knows which report is diagnosable, so it names that report
    here. If n8n worked it out again from the filesystem, the same rule would
    live in two places and could disagree.

    ``failure_report_index`` is always present for a prepared attempt, so a
    caller can read every report. ``failure_report_path`` is added only when a
    created report is marked diagnosable (see ``failure_report.eligibility``).
    A missing key means there is nothing to diagnose; it is never an empty
    string.
    """
    if not index:
        return {}
    attempt = index.get("attempt")
    if not isinstance(attempt, int):
        return {}
    paths = RunPaths(root=Path(run_dir).resolve())
    references = {
        "failure_report_index": repository_relative(_index_path(paths, attempt))
    }
    selected = _first_diagnosable_report(index)
    if selected is not None:
        references["failure_report_path"] = selected
    return references


def read_diagnosis_queue(run_dir: Path, attempt: int) -> dict[str, Any]:
    """Read, validate, and list the diagnosable reports for resume/routing.

    Raises :class:`DiagnosisPreparationError` when the index or a report is
    missing, invalid, or belongs to another run or attempt.
    """
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
                    "scope": report.get("scope", CASE_SCOPE),
                    "test_case_id": report.get("test_case_id"),
                    "assertion_id": report.get("assertion_id"),
                }
            )
    return {
        "run_id": paths.root.name,
        "attempt": attempt,
        "counts": index["counts"],
        "eligible_reports": eligible_reports,
        "failure_report_index": repository_relative(index_path),
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
            if not isinstance(entry, dict) or entry.get("status") != REPORT_CREATED:
                continue
            reports.append(_read_indexed_failure_report(paths, attempt, entry))
    return reports


def _read_diagnosis_index(paths: RunPaths, attempt: int) -> tuple[Path, dict[str, Any]]:
    index_path = _index_path(paths, attempt)
    if not index_path.is_file():
        raise DiagnosisPreparationError(
            f"no diagnosis index for execution attempt {attempt}"
        )
    index = read_json(index_path)
    validate_artifact(DIAGNOSIS_INDEX_SCHEMA, index)
    if index.get("run_id") != paths.root.name or index.get("attempt") != attempt:
        raise DiagnosisPreparationError(
            "diagnosis index identity does not match request"
        )
    return index_path, index


def _read_indexed_failure_report(
    paths: RunPaths, attempt: int, entry: dict[str, Any]
) -> IndexedFailureReport:
    reference = entry.get("report")
    if not isinstance(reference, str) or not reference:
        raise DiagnosisPreparationError(
            "created diagnosis report has no file reference"
        )
    resolved = _attempt_report_path(paths, attempt, reference)
    report = _validated_report(resolved, reference)
    _require_report_identity(report, paths, attempt, reference)
    return IndexedFailureReport(reference=reference, payload=report)


def _attempt_report_path(paths: RunPaths, attempt: int, reference: str) -> Path:
    """The existing report file ``reference`` names, directly in the attempt."""
    candidate = Path(reference)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    resolved = candidate.resolve()
    expected_directory = (_diagnosis_dir(paths, attempt) / REPORTS_DIRNAME).resolve()
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
    return resolved


def _validated_report(resolved: Path, reference: str) -> dict[str, Any]:
    try:
        report = read_json(resolved)
        validate_artifact(FAILURE_REPORT_SCHEMA, report)
    except (OSError, ValueError) as exc:
        raise DiagnosisPreparationError(
            f"diagnosis report is invalid: {reference}: {exc}"
        ) from exc
    return report


def _require_report_identity(
    report: dict[str, Any], paths: RunPaths, attempt: int, reference: str
) -> None:
    # The report schema already requires ``identity`` to be an object.
    identity = report["identity"]
    if identity.get("run_id") != paths.root.name or identity.get("attempt") != attempt:
        raise DiagnosisPreparationError(
            f"diagnosis report identity does not match run/attempt: {reference}"
        )


def _first_diagnosable_report(index: dict[str, Any]) -> str | None:
    """The first report a diagnosis can be asked to read.

    The order is the recorded one (pairs as the execution evidence lists them,
    reports as Surefire listed the failures), so an attempt always selects the
    same report.
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
        and report.get("status") == REPORT_CREATED
        and report.get("eligible") is True
    )


def _record_preparation_error(
    run_dir: Path, attempt: int, error: Exception
) -> dict[str, Any] | None:
    index = _index_document(
        run_id=run_dir.name,
        attempt=attempt,
        execution_evidence=None,
        syntax_evidence=None,
        pairs=[],
        error=f"{type(error).__name__}: {error}",
    )
    try:
        validate_artifact(DIAGNOSIS_INDEX_SCHEMA, index)
        write_json_once(_index_path(RunPaths(root=run_dir.resolve()), attempt), index)
    except OSError:
        return None
    return index


def prepare_execution_diagnosis(run_dir: Path, attempt: int) -> dict[str, Any]:
    """Build every failure report the given execution attempt justifies.

    Returns the index, even when no report could be created. The index is
    written once per attempt: a second call returns the existing one.
    """
    paths = RunPaths(root=Path(run_dir).resolve())
    index_path = _index_path(paths, attempt)
    if index_path.is_file():
        return _existing_index(paths, attempt, index_path)
    index = _prepared_index(paths, attempt)
    validate_artifact(DIAGNOSIS_INDEX_SCHEMA, index)
    _ensure_diagnosis_response_dir(paths, attempt, index)
    write_json_once(index_path, index)
    return index


def _existing_index(paths: RunPaths, attempt: int, index_path: Path) -> dict[str, Any]:
    existing = read_json(index_path)
    validate_artifact(DIAGNOSIS_INDEX_SCHEMA, existing)
    # Also create the trace directory on a re-read, so an index written
    # without one can still be diagnosed without preparing it again.
    _ensure_diagnosis_response_dir(paths, attempt, existing)
    return existing


def _prepared_index(paths: RunPaths, attempt: int) -> dict[str, Any]:
    """Prepare every failed pair of the attempt and index what came of it."""
    evidence_path = paths.stage_attempt_evidence(EXECUTION_STAGE_ID, attempt)
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
    return _index_document(
        run_id=paths.root.name,
        attempt=attempt,
        execution_evidence=repository_relative(evidence_path),
        syntax_evidence=(
            repository_relative(syntax_evidence)
            if syntax_evidence is not None
            else None
        ),
        pairs=pairs,
    )


def _index_document(
    *,
    run_id: str,
    attempt: int,
    execution_evidence: str | None,
    syntax_evidence: str | None,
    pairs: list[dict[str, Any]],
    error: str | None = None,
) -> dict[str, Any]:
    """The diagnosis index; ``error`` is set only when preparation failed."""
    index: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "stage": EXECUTION_STAGE_ID,
        "attempt": attempt,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "execution_evidence": execution_evidence,
        "syntax_evidence": syntax_evidence,
    }
    if error is not None:
        index["error"] = error
    index["counts"] = _index_counts(pairs)
    index["pairs"] = pairs
    return index


def diagnosis_response_dir(run_dir: Path, attempt: int) -> Path:
    """Where a diagnosis of this execution attempt records what it was asked.

    The diagnosis trace (the exact request, the raw answer, the validated
    verdict) belongs to the attempt that produced the evidence, so it is grouped
    by attempt; n8n names the files by its execution id. Python creates the
    directory because the n8n node that writes a file cannot create its folder,
    and running `mkdir` needs a node a default n8n container does not ship.
    """
    responses = RunPaths(Path(run_dir)).response_operation_dir(SOURCE_DIAGNOSIS_DIRNAME)
    return responses / f"{EXECUTION_STAGE_ID}-{attempt_dir_name(attempt)}"


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

    A pair whose test threw and a pair whose assertion lost are both yielded.
    Which of the two happened is read later, per pair, from its evidence.
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
    """The index entry of one failed pair: its reports, or why it has none."""
    entry: dict[str, Any] = {
        "suite": pair.get("suite"),
        "transformation": pair.get("transformation"),
        "observation": pair.get("evidence"),
        "failure_stage": pair.get("failure_stage"),
        "reports": [],
        "skipped": [],
    }
    try:
        evidence = _pair_evidence(
            paths, attempt, pair, execution_evidence, syntax_evidence
        )
        entry["reports"].extend(_pair_reports(evidence))
    except _PairSkipped as skipped:
        entry["skipped"].append(skipped.skip)
    return entry


def _pair_evidence(
    paths: RunPaths,
    attempt: int,
    pair: dict[str, Any],
    execution_evidence: Path,
    syntax_evidence: Path | None,
) -> _PairEvidence:
    """Locate what the pair recorded; raise :class:`_PairSkipped` when it cannot."""
    observation_path = _optional_path(pair.get("evidence"))
    if observation_path is None or not observation_path.is_file():
        raise _PairSkipped("no_recorded_observation", str(pair.get("evidence")))
    if syntax_evidence is None:
        raise _PairSkipped(
            "no_syntax_validation_attempt",
            "the run recorded no syntax-validation attempt to read the parser "
            "verdict for this transformation from",
        )
    execution = read_json(observation_path)
    suite_dir = _optional_path(execution.get("inputs", {}).get("suite", {}).get("path"))
    if suite_dir is None or not suite_dir.is_dir():
        raise _PairSkipped("no_candidate_suite_directory", str(suite_dir))
    archived = archived_execution_evidence(observation_path)
    if archived.directory is None:
        raise _PairSkipped(
            "no_archived_execution_evidence",
            "the execution kept no Maven output or Surefire report, so the "
            "failure cannot be attributed to a concrete assertion",
        )
    return _PairEvidence(
        paths=paths,
        attempt=attempt,
        failure_stage=pair.get("failure_stage"),
        execution=execution,
        observation_path=observation_path,
        suite_dir=suite_dir,
        execution_evidence=execution_evidence,
        syntax_evidence=syntax_evidence,
        reference_execution=_reference_observation(paths, execution),
        surefire_reports=archived.surefire_reports,
    )


def _pair_reports(evidence: _PairEvidence) -> list[dict[str, Any]]:
    """One index entry per recorded test-method failure, or one for the pair."""
    failures = _recorded_failures(evidence.surefire_reports)
    if evidence.failure_stage != FailureStage.ASSERTION_FAILURE:
        failures = [replace(failure, kind=RUNTIME_ERROR_KIND) for failure in failures]
    if not failures:
        # The run failed before Surefire named any test method (the engine
        # refused the transformation, or the harness died during setup). The
        # failure is still real, so the pair itself is the report's subject.
        # No case or assertion is invented.
        return [_prepare_pair_report(evidence)]
    semantic_cases = _read_semantic_cases(evidence.suite_dir)
    if semantic_cases is None:
        raise _PairSkipped("no_semantic_cases", str(evidence.suite_dir))
    return [
        _prepare_report(evidence, failure, semantic_cases) for failure in failures
    ]


def _prepare_report(
    evidence: _PairEvidence,
    failure: SurefireFailure,
    semantic_cases: dict[str, Any],
) -> dict[str, Any]:
    """One report for one recorded test-method failure, or why there is none."""
    try:
        test_case_id, selected_assertion = _attributed_case(semantic_cases, failure)
    except FailureReportError as exc:
        return _refused_entry({"test_method": failure.test_method}, exc)
    attribution = {
        "test_method": failure.test_method,
        "test_case_id": test_case_id,
        "assertion_id": selected_assertion,
    }
    payload = {
        **_request_paths(evidence),
        "test_case_id": test_case_id,
        "assertion_id": selected_assertion,
        "attempt": evidence.attempt,
        "actual_target_models": [
            repository_relative(path)
            for path in _actual_target_models(
                evidence.observation_path, failure.test_method
            )
        ],
        "actual_vs_expected": None,
    }
    # A throw names no assertion, and the file name says so rather than
    # borrowing an assertion id that was never reached.
    output = _report_file(evidence, test_case_id, selected_assertion or "runtime-error")
    return _written_report_entry(
        payload, output, CASE_SCOPE, refused_as=attribution, created_as=attribution
    )


def _attributed_case(
    semantic_cases: dict[str, Any], failure: SurefireFailure
) -> tuple[str, str | None]:
    """The case id and assertion id a recorded failure belongs to."""
    test_case_id = _match_test_case(semantic_cases, failure.test_method)
    if failure.kind != ASSERTION_FAILURE_KIND:
        # A throw lost no assertion, so none is named. Naming one would
        # attribute the failure to a check that never ran.
        return test_case_id, None
    return test_case_id, _match_assertion(semantic_cases, test_case_id, failure.message)


def _prepare_pair_report(evidence: _PairEvidence) -> dict[str, Any]:
    """One report about the execution pair itself, or why there is none."""
    payload = {**_request_paths(evidence), "attempt": evidence.attempt}
    output = _report_file(evidence, "execution-pair")
    return _written_report_entry(
        payload,
        output,
        PAIR_SCOPE,
        refused_as={"scope": PAIR_SCOPE},
        # Explicitly null, so a reader of the index sees that this failure was
        # attributed to no case rather than that the fields went missing.
        created_as={"scope": PAIR_SCOPE, "test_case_id": None, "assertion_id": None},
    )


def _request_paths(evidence: _PairEvidence) -> dict[str, Any]:
    """The recorded paths every report request names.

    Surefire reports and the Maven log are left out on purpose, so the report
    reads them from the archive beside the observation. The workspace copies
    are deleted by the next `mvn clean`.
    """
    return {
        "run_manifest": repository_relative(evidence.paths.manifest),
        "syntax_evidence": repository_relative(evidence.syntax_evidence),
        "execution_evidence": repository_relative(evidence.execution_evidence),
        "generated_execution": repository_relative(evidence.observation_path),
        "reference_execution": (
            repository_relative(evidence.reference_execution)
            if evidence.reference_execution is not None
            else None
        ),
    }


def _written_report_entry(
    payload: dict[str, Any],
    output: Path,
    scope: str,
    *,
    refused_as: dict[str, Any],
    created_as: dict[str, Any],
) -> dict[str, Any]:
    """Write one report and return its index entry, created or refused.

    ``refused_as`` and ``created_as`` are the fields that say which failure
    the entry is about.
    """
    try:
        report = write_report(payload, output, scope=scope)
    except FailureReportError as exc:
        return _refused_entry(refused_as, exc)
    diagnosis = report["source_diagnosis"]
    return {
        "status": REPORT_CREATED,
        **created_as,
        "report": repository_relative(output),
        "eligible": diagnosis["eligible"],
        "reason": diagnosis["reason"],
    }


def _refused_entry(
    attribution: dict[str, Any], error: FailureReportError
) -> dict[str, Any]:
    return {"status": REPORT_REFUSED, **attribution, "detail": str(error)}


def _recorded_failures(reports: tuple[Path, ...]) -> list[SurefireFailure]:
    """Every failed or erroring ``<testcase>`` in the archived reports, in order.

    Errors count too: a validated test that throws on a generated
    transformation has failed against it. A case with both an error and a
    failure counts as an error (see :func:`testcase_outcome`).
    """
    failures: list[SurefireFailure] = []
    for path in reports:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            # An unreadable report is not evidence of a failure. The file stays
            # archived, and nothing is inferred from it.
            continue
        for case in root.iter("testcase"):
            failure = _recorded_failure(case)
            if failure is not None:
                failures.append(failure)
    return failures


def _recorded_failure(case: ET.Element) -> SurefireFailure | None:
    status, node = testcase_outcome(case)
    if node is None:
        return None
    return SurefireFailure(
        kind=RUNTIME_ERROR_KIND if status == "error" else ASSERTION_FAILURE_KIND,
        test_method=str(case.get("name") or ""),
        message=str(node.get("message") or ""),
    )


def _match_test_case(semantic_cases: dict[str, Any], test_method: str) -> str:
    """The id of the one semantic case whose rendered method is ``test_method``."""
    method_name = testcase_method_name(test_method)
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise FailureReportError(f"{SEMANTIC_CASES_FILE} has no tests array")
    matching = [
        case_id(test)
        for test in tests
        if isinstance(test, dict) and rendered_method_name(test) == method_name
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

    The harness prints the assertion's message and may append detail
    (``... missing X``, ``... ==> expected: <1> but was: <0>``), so the message
    is matched as a prefix. When two assertions render the same message, the
    failure is refused rather than given to the first one.
    """
    tests = semantic_cases.get("tests")
    test_case = next(
        (
            test
            for test in tests
            if isinstance(test, dict) and case_id(test) == test_case_id
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


def _matching_assertion_ids(assertions: list[Any], stripped_message: str) -> list[str]:
    """Return assertion IDs whose rendered messages match the recorded prefix."""
    matching: list[str] = []
    for position, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        # Use the renderer's own rule. A copy of the rule here could drift
        # from it without any test failing.
        rendered = assertion_message(assertion)
        if rendered and stripped_message.startswith(rendered):
            matching.append(assertion_id(assertion, position))
    return matching


def _actual_target_models(observation_path: Path, test_method: str) -> list[Path]:
    """The actual output models this execution wrote for this test case.

    They live beside the observation, under ``snapshots/<test-method>/``, so
    they belong to this transformation, suite, and case only. A folder shared by
    all suites of one transformation could make a diagnosis cite another
    suite's output.
    """
    directory = observation_path.parent / SNAPSHOTS_DIRNAME / test_method
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.xmi") if path.is_file())


def _reference_observation(paths: RunPaths, execution: dict[str, Any]) -> Path | None:
    """This run's reference observation for the same suite, when it recorded one."""
    try:
        candidate = (
            paths.observations_dir
            / str(execution["task"])
            / str(execution["llm"])
            / str(execution["strategy"])
            / str(execution["suite_id"])
            / OBSERVATION_FILENAME
        )
    except KeyError:
        return None
    return candidate if candidate.is_file() else None


def _read_semantic_cases(suite_dir: Path) -> dict[str, Any] | None:
    path = suite_dir / SEMANTIC_CASES_FILE
    if not path.is_file():
        return None
    payload = read_json(path)
    return payload if isinstance(payload, dict) else None


def _latest_syntax_evidence(paths: RunPaths) -> Path | None:
    attempts = paths.stage_attempts_dir(SYNTAX_VALIDATION_STAGE_ID)
    if not attempts.is_dir():
        return None
    for attempt in sorted(existing_attempts(attempts), reverse=True):
        evidence = paths.stage_attempt_evidence(SYNTAX_VALIDATION_STAGE_ID, attempt)
        if evidence.is_file():
            return evidence
    return None


def diagnosis_reports_location(attempt: int) -> str:
    """The folder of one execution attempt's failure reports, relative to the run.

    A diagnosis names the report it judged by a run-relative path.
    """
    return (_attempt_location(attempt) / REPORTS_DIRNAME).as_posix()


def _attempt_location(attempt: int) -> PurePosixPath:
    return PurePosixPath(
        DIAGNOSIS_DIRNAME, EXECUTION_STAGE_ID, attempt_dir_name(attempt)
    )


def _diagnosis_dir(paths: RunPaths, attempt: int) -> Path:
    return paths.root / _attempt_location(attempt)


def _index_path(paths: RunPaths, attempt: int) -> Path:
    return _diagnosis_dir(paths, attempt) / INDEX_FILENAME


def diagnosis_index_path(run_dir: Path, attempt: int) -> Path:
    """Where the diagnosis index of one execution attempt of a run lives."""
    return _index_path(RunPaths(root=Path(run_dir).resolve()), attempt)


def _report_file(evidence: _PairEvidence, *subject: str) -> Path:
    """The report file for one failure of the pair; ``subject`` names the failure."""
    # The transformation hash is part of the name because one attempt can pair
    # the same suite with several generated transformations, and two reports
    # about different transformations are different evidence.
    execution = evidence.execution
    transformation_hash = _transformation_hash(execution)
    name = "__".join(
        _safe(part)
        for part in (
            transformation_hash[:REPORT_NAME_HASH_CHARS] or "transformation",
            str(execution.get("suite_id", "suite")),
            *subject,
        )
    )
    reports_dir = _diagnosis_dir(evidence.paths, evidence.attempt) / REPORTS_DIRNAME
    return reports_dir / f"{name}.json"


def _transformation_hash(execution: dict[str, Any]) -> str:
    return str(execution.get("inputs", {}).get("transformation", {}).get("sha256", ""))


def _index_counts(pairs: list[dict[str, Any]]) -> dict[str, int]:
    """Counts about the prepared evidence only.

    None of these is an experiment metric. The stage's own counts (passed,
    failed, evaluated) were written before preparation and are never changed
    by it, so a report created here cannot change a semantic result.
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
        if report["status"] == REPORT_CREATED:
            created.append(report)
        elif report["status"] == REPORT_REFUSED:
            refused_count += 1
        if report.get("eligible"):
            eligible_count += 1

    return {
        "reports_created": len(created),
        "reports_refused": refused_count,
        "pair_level_reports": sum(
            1 for report in created if report.get("scope") == PAIR_SCOPE
        ),
        "diagnosis_eligible": eligible_count,
    }



def _safe(value: str) -> str:
    cleaned = SAFE_NAME.sub("-", value).strip("-")
    return cleaned or "unnamed"


def _optional_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate
