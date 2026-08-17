"""Assemble one per-assertion semantic-test failure report.

The module only aggregates facts that earlier stages recorded.  It does not
compare models, classify the source of a failure, call an LLM, or choose a
workflow route.  In particular, ``actual_vs_expected`` must come from the
comparator or harness that observed the mismatch; this module refuses to invent
that evidence.

Run it through the experiment orchestrator with::

    llm4mtl diagnosis report \
      --request request.json --output artifacts/work/.../failure-report.json

The module also keeps a direct ``python -m llm4mtl.semantic_tests.failure_report``
entry point for narrow local use; both paths call the same assembler.

The request is one JSON object with these fields::

    {
      "run_manifest": "artifacts/work/runs/<run>/manifest.json",
      "syntax_evidence": ".../stages/syntax-validation/.../evidence.json",
      "execution_evidence": ".../stages/execution/attempts/attempt-001/evidence.json",
      "generated_execution": ".../suite_execution.json",
      "reference_execution": ".../suite_execution.json",  # optional
      "test_case_id": "case_name",
      "assertion_id": "assertion-001",
      "attempt": 1,
      "actual_target_models": [".../snapshot.xmi"],
      "surefire_reports": [".../TEST-GeneratedTest.xml"],   # optional, see below
      "execution_log": ".../execution.log",                 # optional
      "actual_vs_expected": {                                # optional, see below
        "missing_elements": [],
        "extra_elements": [],
        "wrong_types": [],
        "wrong_attributes": [],
        "reference_mismatches": []
      }
    }

``actual_vs_expected`` is the model-level comparator difference.  It is optional
because no comparator produces it yet, and inventing one here is exactly what
this module refuses to do.  What the report records without it is what the run
observed: the actual target-model snapshots the harness wrote, the
``expected``/``actual`` values JUnit printed read verbatim, and the recorded
exception.  A diagnosis-eligible failure needs a syntactically valid
transformation, a suite that passed on the reference, a real failure of the
pairing, the transformed input, and at least one of those observed facts.

Both JUnit outcomes are real failures here.  An assertion that was evaluated and
lost names the assertion it lost; a throw before any verdict names none, and
``assertion_id`` is then ``null`` — the exception and its stack trace are the
evidence, and ``expected``/``actual`` stay ``null`` rather than being
reconstructed.  A timeout or an infrastructure failure is excluded instead,
because neither says anything about the pairing.

``assertion_id`` is either an explicit assertion ``id`` from
``semantic_cases.json``, the stable positional id ``assertion-NNN``, or ``null``
for a runtime throw.  Input
models, the generated transformation and suite, the reviewed task description,
and exact metamodels are resolved from the recorded identities.  Every input
path must stay inside the repository, and the output must stay under
``artifacts/work``.  The output is created once and never overwritten.

``surefire_reports`` and ``execution_log`` may be omitted, and normally should
be: the run archives its own Maven output and Surefire XML beside each execution
observation, and that archive is the only copy that still describes the
execution once the next pair's ``mvn clean`` has run.  Omitting them reads the
archive; naming them explicitly still works for evidence held elsewhere.  A
request that omits them for an execution with no archive is refused rather than
producing a report whose runtime evidence is silently empty.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_method_name
from llm4mtl.semantic_tests.execution_evidence import archived_execution_evidence
from llm4mtl.serialization.json_io import read_json, write_json_once
from llm4mtl.transformation_execution.hashing import directory_sha256, file_sha256

SCHEMA_VERSION = "1.0"
# Two report types, kept apart by what the run was able to attribute the failure
# to. A per-case report is about one test case and, for an assertion failure,
# one assertion. A pair-level report is about the execution of one suite against
# one transformation and nothing narrower: it exists for failures that happened
# before Surefire could attribute anything to a test method, and it names no
# case and no assertion rather than inventing one to fill the shape.
CASE_REPORT_TYPE = "semantic_test_case_failure"
PAIR_REPORT_TYPE = "semantic_execution_pair_failure"
SYSTEM_ERR_EXCERPT_CHARS = 4000
DIFF_FIELDS = (
    "missing_elements",
    "extra_elements",
    "wrong_types",
    "wrong_attributes",
    "reference_mismatches",
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# JUnit renders a failed equality assertion as
# ``<message> ==> expected: <X> but was: <Y>``. Reading X and Y back is
# observation, not inference: the values are the ones the harness printed. Any
# message that does not have exactly this shape yields ``None`` for both rather
# than a guess reconstructed from prose.
ASSERTION_OUTCOME_SEPARATOR = " but was: <"
ASSERTION_OUTCOME_PREFIX = "expected: <"

# The report cites the Maven log rather than copying it. The complete,
# untruncated stream is already archived beside the observation, and a build log
# can run to thousands of lines: inlining it would put the same bytes into every
# per-assertion report of the same execution and then into the diagnosis prompt,
# where it drowns the evidence Python already extracted. The tail is what
# carries the failure summary and the `[ERROR]` lines.
EXECUTION_LOG_EXCERPT_LINES = 120
EXECUTION_LOG_EXCERPT_CHARS = 8000
# The diagnosis prompt gets less than the report keeps: only the lines Maven
# itself marked, and only the last of those.
MAVEN_BUNDLE_LINES = 40
GENERATED_EXECUTION_LABEL = "generated execution"

CASE_REQUEST_FIELDS = frozenset(
    {
        "actual_target_models",
        "actual_vs_expected",
        "assertion_id",
        "attempt",
        "execution_evidence",
        "execution_log",
        "generated_execution",
        "reference_execution",
        "run_manifest",
        "surefire_reports",
        "syntax_evidence",
        "test_case_id",
    }
)
PAIR_REQUEST_FIELDS = frozenset(
    {
        "attempt",
        "execution_evidence",
        "execution_log",
        "generated_execution",
        "reference_execution",
        "run_manifest",
        "surefire_reports",
        "syntax_evidence",
    }
)


class FailureReportError(ValueError):
    """Raised when recorded evidence cannot form a trustworthy report."""


@dataclass(frozen=True)
class ReportRequest:
    """Validated paths and selectors for one report assembly."""

    run_manifest: Path
    syntax_evidence: Path
    execution_evidence: Path
    generated_execution: Path
    reference_execution: Path | None
    test_case_id: str
    assertion_id: str | None
    attempt: int
    actual_target_models: tuple[Path, ...]
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None
    actual_vs_expected: dict[str, list[Any]] | None

    @classmethod
    def from_payload(cls, payload: object) -> ReportRequest:
        """Validate the request boundary and resolve every supplied path."""
        request_payload = _request_payload(payload, CASE_REQUEST_FIELDS)

        test_case_id = _required_string(request_payload, "test_case_id")
        # Null is the honest value for a runtime throw: the harness never
        # reached an assertion, so naming one would attribute the failure to a
        # check that did not run.
        assertion_id = (
            None
            if request_payload.get("assertion_id") is None
            else _required_string(request_payload, "assertion_id")
        )
        attempt = _positive_attempt(request_payload)

        actual_vs_expected = _validate_difference(
            request_payload.get("actual_vs_expected")
        )
        generated_execution = _input_path(
            request_payload.get("generated_execution"), "generated_execution"
        )
        # The workspace those reports were produced in is wiped by the next
        # `mvn clean`, so a request that named them there would break as soon as
        # the run continued. Omitting them therefore means "read the run's own
        # archive", which is the only copy that still describes this execution.
        #
        # Nothing is inferred either way: an archive that recorded no Surefire
        # report yields no report, and a request that names neither an explicit
        # path nor an archived execution is refused rather than producing a
        # report whose runtime evidence is silently empty.
        archived = archived_execution_evidence(generated_execution)
        if "surefire_reports" not in request_payload and archived.directory is None:
            raise FailureReportError(
                "surefire_reports must be an array of paths, or the generated "
                "execution must have archived execution evidence beside it"
            )
        return cls(
            run_manifest=_input_path(
                request_payload.get("run_manifest"), "run_manifest"
            ),
            syntax_evidence=_input_path(
                request_payload.get("syntax_evidence"), "syntax_evidence"
            ),
            execution_evidence=_input_path(
                request_payload.get("execution_evidence"), "execution_evidence"
            ),
            generated_execution=generated_execution,
            reference_execution=_optional_input_path(
                request_payload.get("reference_execution"), "reference_execution"
            ),
            test_case_id=test_case_id,
            assertion_id=assertion_id,
            attempt=attempt,
            actual_target_models=_input_paths(
                request_payload.get("actual_target_models"), "actual_target_models"
            ),
            surefire_reports=(
                _input_paths(
                    request_payload["surefire_reports"], "surefire_reports"
                )
                if "surefire_reports" in request_payload
                else archived.surefire_reports
            ),
            execution_log=(
                _optional_input_path(
                    request_payload.get("execution_log"), "execution_log"
                )
                if "execution_log" in request_payload
                else archived.execution_log
            ),
            actual_vs_expected=actual_vs_expected,
        )


def build_failure_report(request: ReportRequest) -> dict[str, Any]:
    """Build a self-contained report for one recorded failure.

    Diagnosis eligibility is derived from recorded facts only — the parser
    verdict, the reference result, the generated-transformation observation, and
    what evidence survived.  See :func:`_diagnosis_reason` for the conditions.
    """
    manifest = _read_object(request.run_manifest, "run manifest")
    identity = _identity(manifest, request.attempt)
    generated_execution = _read_execution(
        request.generated_execution, identity, GENERATED_EXECUTION_LABEL
    )
    suite_dir, transformation_path = _generated_inputs(generated_execution)
    _verify_recorded_hashes(generated_execution, suite_dir, transformation_path)
    execution_stage_evidence = _execution_stage_evidence(
        request.execution_evidence,
        request.generated_execution,
        suite_dir,
        transformation_path,
        request.attempt,
        generated_execution,
    )

    semantic_cases_path = suite_dir / "semantic_cases.json"
    semantic_cases = _read_object(semantic_cases_path, "semantic cases")
    test_case = _select_test_case(semantic_cases, request.test_case_id)
    assertion = _select_assertion(test_case, request.assertion_id)

    syntax_check = _syntax_check(
        _read_object(request.syntax_evidence, "syntax evidence"),
        transformation_path,
    )
    observation = _observation(generated_execution, GENERATED_EXECUTION_LABEL)
    semantic_status = _semantic_status(observation)

    task_description = _task_description(identity, manifest)
    metamodels = _metamodel_artifacts(manifest)
    input_models = _input_models(test_case, suite_dir)
    expected_target_models = _expected_target_models(test_case, suite_dir)

    actual_target_models = [
        _text_artifact(path) for path in request.actual_target_models
    ]
    surefire_evidence = _surefire_evidence(
        request.surefire_reports, request.test_case_id
    )
    failure = _recorded_failure_view(surefire_evidence)
    execution_error = {
        "error_summary": str(observation.get("error_summary", "")),
        "exceptions": surefire_evidence["exceptions"],
        "stack_traces": surefire_evidence["stack_traces"],
        "execution_log": (
            _log_excerpt(request.execution_log)
            if request.execution_log is not None
            else None
        ),
        "surefire": surefire_evidence["test_cases"],
    }

    reference_result = _reference_result(request.reference_execution, identity)
    versions = {
        "generated_transformation": {
            "sha256": file_sha256(transformation_path),
            "path": _repository_path(transformation_path),
        },
        "generated_test": {
            "sha256": directory_sha256(suite_dir),
            "path": _repository_path(suite_dir),
            "renderer_version": manifest.get("provenance", {}).get(
                "renderer_version"
            ),
        },
    }

    difference = (
        {"available": True, **request.actual_vs_expected}
        if request.actual_vs_expected is not None
        else {"available": False, **{field: None for field in DIFF_FIELDS}}
    )
    # What the run observed about this failure, as separate facts. Diagnosis
    # needs at least one of them: without any, the LLM would be asked what went
    # wrong while being told nothing about what actually happened. An assertion
    # failure and a runtime throw satisfy this differently and both count — a
    # thrown exception with its stack trace is evidence, and refusing to
    # diagnose it would drop exactly the failures a transformation defect most
    # often produces.
    observed_failure_evidence = {
        "target_model_snapshots": len(actual_target_models),
        "assertion_expected_actual": failure is not None
        and failure["extraction"] == "junit_assertion_message",
        "structured_difference": request.actual_vs_expected is not None,
        "recorded_exception": bool(surefire_evidence["exceptions"]),
    }
    diagnosis_reason = _diagnosis_reason(
        syntax_check,
        observation,
        reference_result,
        input_models=input_models,
        observed_failure_evidence=observed_failure_evidence,
    )
    is_diagnosis_eligible = diagnosis_reason == "parser_passed_and_semantic_test_failed"
    if (
        is_diagnosis_eligible
        and failure is not None
        and failure["kind"] == "assertion_failure"
    ):
        # Only an assertion failure claims to be about one assertion, so only it
        # has to prove that the selected assertion is the one that lost.
        _require_concrete_assertion_failure(test_case, assertion, surefire_evidence)

    test_case_result = {
        "test_case_id": request.test_case_id,
        "assertion_id": request.assertion_id,
        "semantic_status": semantic_status,
        "syntax_check": syntax_check,
        "test_case": test_case,
        "assertion": assertion,
        "input_model": {
            "models": input_models,
            "changes": test_case.get("changes", []),
        },
        "expected_output_or_properties": {
            "assertion": assertion,
            "target_models": expected_target_models,
        },
        "actual_target_model": actual_target_models,
        "actual_vs_expected": difference,
        "failure": failure,
        "observed_failure_evidence": observed_failure_evidence,
        "execution": {
            "observation": observation,
            "stage_evidence": execution_stage_evidence,
            "error": execution_error,
        },
        "reference_transformation_result": reference_result,
        "versions": versions,
    }

    evidence_bundle = (
        _evidence_bundle(
            request=request,
            task_description=task_description,
            metamodels=metamodels,
            transformation_path=transformation_path,
            test_case=test_case,
            assertion=assertion,
            failure=failure,
            syntax_check=syntax_check,
            observation=observation,
            reference_result=reference_result,
            test_case_result=test_case_result,
            actual_target_models=actual_target_models,
            difference=difference,
            surefire_evidence=surefire_evidence,
        )
        if is_diagnosis_eligible
        else None
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": CASE_REPORT_TYPE,
        "identity": identity,
        "task_context": {
            "original_description": task_description,
            "metamodel_constraints": metamodels,
        },
        "test_case_result": test_case_result,
        "source_diagnosis": {
            "eligible": is_diagnosis_eligible,
            "reason": diagnosis_reason,
            "evidence_bundle": evidence_bundle,
            "allowed_classifications": [
                "transformation_defect",
                "test_defect",
                "ambiguous",
            ],
            "required_result_fields": [
                "classification",
                "confidence",
                "reasoning_summary",
                "evidence",
                "test_case_id",
            ],
        },
    }


def _evidence_bundle(
    *,
    request: ReportRequest,
    task_description: dict[str, Any],
    metamodels: list[dict[str, Any]],
    transformation_path: Path,
    test_case: dict[str, Any],
    assertion: dict[str, Any] | None,
    failure: dict[str, Any] | None,
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
    test_case_result: dict[str, Any],
    actual_target_models: list[dict[str, Any]],
    difference: dict[str, Any],
    surefire_evidence: dict[str, Any],
) -> dict[str, Any]:
    """The prompt-shaped subset of the report, and only that.

    The stored report keeps everything the run recorded — hashes, the whole
    stage-evidence document, every Surefire entry. The bundle is what a
    diagnosis is actually asked to read, so it carries each fact once, in the
    form a reader needs: contents without their hashes, the reference result as
    a verdict rather than a nested document, the execution as a summary of what
    failed, and the build log as a bounded excerpt. Sending the report verbatim
    would spend most of the prompt on provenance the LLM cannot use and on the
    same JSON document quoted twice.
    """
    stack_traces = surefire_evidence["stack_traces"]
    return {
        "original_task_description": task_description["content"],
        "relevant_source_and_target_metamodel_constraints": [
            _cited(metamodel) for metamodel in metamodels
        ],
        "generated_transformation": _cited(_text_artifact(transformation_path)),
        "failing_test_case_or_assertion": {
            "test_case_id": request.test_case_id,
            "assertion_id": request.assertion_id,
            "test_case": test_case,
            "assertion": assertion,
        },
        "input_model": [
            {"model": entry["model"], **_cited(entry["artifact"])}
            for entry in test_case_result["input_model"]["models"]
        ],
        "changes": test_case_result["input_model"]["changes"],
        "expected_output_or_properties": test_case_result[
            "expected_output_or_properties"
        ],
        "syntax_status": syntax_check,
        "reference_transformation_result": {
            "status": reference_result["status"],
            "assertions_passed": (
                reference_result["observation"]["assertions_passed"]
                if reference_result["observation"] is not None
                else None
            ),
        },
        "generated_execution_summary": {
            "failure_stage": observation.get("failure_stage"),
            "assertions_evaluated": observation.get("assertions_evaluated"),
            "assertions_passed": observation.get("assertions_passed"),
            "error_summary": observation.get("error_summary"),
            "failure_kind": failure["kind"] if failure else None,
            "failure_type": failure["failure_type"] if failure else None,
            "message": failure["message"] if failure else None,
            "expected": failure["expected"] if failure else None,
            "actual": failure["actual"] if failure else None,
        },
        "actual_target_model": [_cited(model) for model in actual_target_models],
        "structured_actual_vs_expected_difference": difference,
        # A stack trace is what identifies where a throw came from, so a runtime
        # failure keeps it. An assertion failure does not need it: its message
        # already carries the mismatch, and the trace is harness plumbing.
        "stack_traces": (
            stack_traces if failure and failure["kind"] == "runtime_error" else []
        ),
        "maven_log_excerpt": _relevant_log_lines(
            test_case_result["execution"]["error"]["execution_log"]
        ),
    }


def _relevant_log_lines(cited_log: dict[str, Any] | None) -> dict[str, Any] | None:
    """The build-log lines that say something about this run's outcome.

    A Maven log is mostly reactor progress. The lines that matter are the ones
    the build itself marked — errors, warnings, the Surefire summary, the build
    verdict — and selecting by those markers is a filter over the log's own
    output, not a judgement about the failure. The report keeps the wider
    excerpt and the archive keeps the whole stream, so nothing is lost by
    sending less.
    """
    if cited_log is None:
        return None
    lines = [
        line
        for line in cited_log["excerpt"].splitlines()
        if line.startswith(("[ERROR]", "[WARNING]"))
        or "Tests run:" in line
        or "BUILD " in line
    ]
    return {
        "path": cited_log["path"],
        "lines": cited_log["lines"],
        "selected": "marked lines only; the full log is at `path`",
        "excerpt": "\n".join(lines[-MAVEN_BUNDLE_LINES:]),
    }


def _cited(artifact: dict[str, Any]) -> dict[str, Any]:
    """One artifact as the prompt needs it: where it is and what is in it."""
    return {"path": artifact["path"], "content": artifact["content"]}


def write_failure_report(request: ReportRequest, output: Path) -> dict[str, Any]:
    """Create one immutable report under ``artifacts/work`` and return it."""
    resolved_output = _output_path(output)
    report = build_failure_report(request)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        repository_output = _repository_path(resolved_output)
        raise FailureReportError(
            f"report already exists and is immutable: {repository_output}"
        ) from exc
    return report


@dataclass(frozen=True)
class PairReportRequest:
    """Validated paths for one pair-level report.

    Deliberately narrower than :class:`ReportRequest`: there is no
    ``test_case_id``, no ``assertion_id``, no actual target model and no
    comparator difference, because a failure that never reached a test method
    has none of them. Every field that a per-case report would fill from the
    case is simply absent here rather than defaulted.
    """

    run_manifest: Path
    syntax_evidence: Path
    execution_evidence: Path
    generated_execution: Path
    reference_execution: Path | None
    attempt: int
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None

    @classmethod
    def from_payload(cls, payload: object) -> PairReportRequest:
        """Validate the pair-level request and resolve every supplied path."""
        request_payload = _request_payload(payload, PAIR_REQUEST_FIELDS)
        attempt = _positive_attempt(request_payload)

        generated_execution = _input_path(
            request_payload.get("generated_execution"), "generated_execution"
        )
        archived = archived_execution_evidence(generated_execution)
        return cls(
            run_manifest=_input_path(
                request_payload.get("run_manifest"), "run_manifest"
            ),
            syntax_evidence=_input_path(
                request_payload.get("syntax_evidence"), "syntax_evidence"
            ),
            execution_evidence=_input_path(
                request_payload.get("execution_evidence"), "execution_evidence"
            ),
            generated_execution=generated_execution,
            reference_execution=_optional_input_path(
                request_payload.get("reference_execution"), "reference_execution"
            ),
            attempt=attempt,
            surefire_reports=(
                _input_paths(
                    request_payload["surefire_reports"], "surefire_reports"
                )
                if "surefire_reports" in request_payload
                else archived.surefire_reports
            ),
            execution_log=(
                _optional_input_path(
                    request_payload.get("execution_log"), "execution_log"
                )
                if "execution_log" in request_payload
                else archived.execution_log
            ),
        )


def build_pair_failure_report(request: PairReportRequest) -> dict[str, Any]:
    """Build a report about one suite/transformation execution as a whole.

    This is the report for a failure the run could not attribute to any test
    method: the engine refused the transformation, the harness died before
    Surefire wrote a per-test entry, and so on. It is still a real failure of a
    reference-validated suite against a generated transformation, which is
    exactly what Source Diagnosis exists to attribute — so the evidence that
    does exist is assembled, and the evidence that does not is left absent.

    Nothing is narrowed by guessing. ``test_case_id`` and ``assertion_id`` are
    null, ``expected`` and ``actual`` are null, and the whole generated test is
    supplied instead of a selected case, because which case failed is precisely
    what the run did not record.
    """
    manifest = _read_object(request.run_manifest, "run manifest")
    identity = _identity(manifest, request.attempt)
    generated_execution = _read_execution(
        request.generated_execution, identity, GENERATED_EXECUTION_LABEL
    )
    suite_dir, transformation_path = _generated_inputs(generated_execution)
    _verify_recorded_hashes(generated_execution, suite_dir, transformation_path)
    execution_stage_evidence = _execution_stage_evidence(
        request.execution_evidence,
        request.generated_execution,
        suite_dir,
        transformation_path,
        request.attempt,
        generated_execution,
    )

    syntax_check = _syntax_check(
        _read_object(request.syntax_evidence, "syntax evidence"),
        transformation_path,
    )
    observation = _observation(generated_execution, GENERATED_EXECUTION_LABEL)
    reference_result = _reference_result(request.reference_execution, identity)
    surefire = _pair_surefire_evidence(request.surefire_reports)
    execution_log = (
        _log_excerpt(request.execution_log)
        if request.execution_log is not None
        else None
    )

    generated_test = _text_artifact(suite_dir / "semantic_cases.json")
    failure = {
        "scope": "execution_pair",
        "failure_stage": observation.get("failure_stage"),
        "failure_type": surefire["failure_type"],
        "message": surefire["message"] or str(observation.get("error_summary", "")),
        # A failure that reached no assertion produced no expected and no
        # actual. Both stay null; the harness never computed either.
        "expected": None,
        "actual": None,
        "extraction": "unavailable",
    }
    execution_error = {
        "error_summary": str(observation.get("error_summary", "")),
        "exceptions": surefire["exceptions"],
        "stack_traces": surefire["stack_traces"],
        "system_err": surefire["system_err"],
        "execution_log": execution_log,
        "surefire_reports": surefire["reports"],
    }
    preserved_failure_evidence = {
        "recorded_exception": bool(surefire["exceptions"]),
        "system_err": bool(surefire["system_err"]),
        "error_summary": bool(str(observation.get("error_summary", "")).strip()),
        "maven_log": execution_log is not None,
    }

    diagnosis_reason = _pair_diagnosis_reason(
        syntax_check,
        observation,
        reference_result,
        execution_attempted=execution_log is not None or bool(surefire["reports"]),
        per_test_failures=surefire["test_failures"],
        preserved_failure_evidence=preserved_failure_evidence,
    )
    is_diagnosis_eligible = (
        diagnosis_reason == "parser_passed_and_execution_failed_before_any_test"
    )

    task_description = _task_description(identity, manifest)
    metamodels = _metamodel_artifacts(manifest)

    pair_result = {
        # Stated as null rather than omitted: a reader comparing report types
        # must see that this failure has no case and no assertion, not wonder
        # whether the fields were dropped.
        "test_case_id": None,
        "assertion_id": None,
        "semantic_status": _semantic_status(observation),
        "syntax_check": syntax_check,
        "generated_test": {
            **generated_test,
            "suite_id": generated_execution.get("suite_id"),
            "test_case_ids": _test_case_ids(generated_test["content"]),
        },
        "generated_transformation": _text_artifact(transformation_path),
        "failure": failure,
        "preserved_failure_evidence": preserved_failure_evidence,
        "execution": {
            "observation": observation,
            "stage_evidence": execution_stage_evidence,
            "error": execution_error,
        },
        "reference_transformation_result": reference_result,
        "versions": {
            "generated_transformation": {
                "sha256": file_sha256(transformation_path),
                "path": _repository_path(transformation_path),
            },
            "generated_test": {
                "sha256": directory_sha256(suite_dir),
                "path": _repository_path(suite_dir),
                "renderer_version": manifest.get("provenance", {}).get(
                    "renderer_version"
                ),
            },
        },
    }

    evidence_bundle = (
        _pair_evidence_bundle(
            task_description=task_description,
            metamodels=metamodels,
            transformation_path=transformation_path,
            generated_test=pair_result["generated_test"],
            syntax_check=syntax_check,
            observation=observation,
            reference_result=reference_result,
            failure=failure,
            surefire=surefire,
            execution_log=execution_log,
        )
        if is_diagnosis_eligible
        else None
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": PAIR_REPORT_TYPE,
        "identity": identity,
        "task_context": {
            "original_description": task_description,
            "metamodel_constraints": metamodels,
        },
        "pair_result": pair_result,
        "source_diagnosis": {
            "eligible": is_diagnosis_eligible,
            "reason": diagnosis_reason,
            "evidence_bundle": evidence_bundle,
            "allowed_classifications": [
                "transformation_defect",
                "test_defect",
                "ambiguous",
            ],
            "required_result_fields": [
                "classification",
                "confidence",
                "reasoning_summary",
                "evidence",
            ],
        },
    }


def _pair_diagnosis_reason(
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
    *,
    execution_attempted: bool,
    per_test_failures: list[dict[str, Any]],
    preserved_failure_evidence: dict[str, bool],
) -> str:
    """Why this pair failure is or is not one Source Diagnosis may be asked about.

    Same first conditions as the per-case rule, plus two that are specific to
    this report type: the execution has to have actually been attempted, and no
    narrower attribution may exist. A run that *did* name a failing test method
    is not a pair-level case — it has a per-case report, and producing both
    would put the same failure into the population twice.
    """
    if syntax_check["status"] != "passed":
        return "transformation_parser_check_failed"
    if observation["assertions_passed"] is True:
        return "semantic_test_passed"
    if observation.get("timed_out") is True or observation.get("failure_stage") in {
        "timeout",
        "infrastructure",
    }:
        return "failure_not_attributable_to_the_pairing"
    if reference_result.get("status") != "passed":
        return "reference_result_not_passing"
    if not execution_attempted:
        return "execution_not_attempted"
    if per_test_failures:
        return "per_test_failure_available"
    if not any(preserved_failure_evidence.values()):
        return "no_preserved_failure_evidence"
    return "parser_passed_and_execution_failed_before_any_test"


def _pair_surefire_evidence(report_paths: Sequence[Path]) -> dict[str, Any]:
    """What the archived reports say about a run with no per-test failure.

    ``test_failures`` is the proof that no narrower attribution exists: it lists
    every test method the reports *did* mark, so a caller can see that the
    pair-level report was not used to bypass a per-case one. The exceptions come
    from the testsuite element itself, which is where a harness that died before
    running a test writes them.
    """
    test_failures: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    system_err: list[str] = []
    reports: list[str] = []
    for path in report_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        reports.append(_repository_path(path))
        test_failures.extend(_pair_test_failures(root))
        report_exceptions, report_traces = _suite_failures(root)
        exceptions.extend(report_exceptions)
        stack_traces.extend(report_traces)
        system_err.extend(_system_err_excerpts(root))
    return {
        "test_failures": test_failures,
        "exceptions": exceptions,
        "stack_traces": stack_traces,
        "system_err": system_err,
        "reports": reports,
        "failure_type": exceptions[0]["type"] if exceptions else None,
        "message": exceptions[0]["message"] if exceptions else "",
    }


def _pair_test_failures(root: ET.Element) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        error = case.find("error")
        node = error if error is not None else case.find("failure")
        if node is None:
            continue
        failures.append(
            {
                "test_class": case.get("classname"),
                "test_method": case.get("name"),
                "status": "error" if error is not None else "failed",
            }
        )
    return failures


def _suite_failures(
    root: ET.Element,
) -> tuple[list[dict[str, str]], list[str]]:
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    for node in [*root.findall("error"), *root.findall("failure")]:
        exceptions.append(
            {
                "type": str(node.get("type") or node.tag),
                "message": str(node.get("message") or ""),
            }
        )
        trace = (node.text or "").strip()
        if trace:
            stack_traces.append(trace)
    return exceptions, stack_traces


def _system_err_excerpts(root: ET.Element) -> list[str]:
    excerpts: list[str] = []
    for stream in root.findall("system-err"):
        text = (stream.text or "").strip()
        if text:
            excerpts.append(text[-SYSTEM_ERR_EXCERPT_CHARS:])
    return excerpts


def _pair_evidence_bundle(
    *,
    task_description: dict[str, Any],
    metamodels: list[dict[str, Any]],
    transformation_path: Path,
    generated_test: dict[str, Any],
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
    failure: dict[str, Any],
    surefire: dict[str, Any],
    execution_log: dict[str, Any] | None,
) -> dict[str, Any]:
    """The prompt-shaped subset of a pair-level report.

    It answers the same question as the per-case bundle from less: what the task
    was, what the transformation and the test look like, that the same test
    passed on the reference, and how the execution died. What it must not do is
    imply a failing case that the run never identified.
    """
    return {
        "original_task_description": task_description["content"],
        "relevant_source_and_target_metamodel_constraints": [
            _cited(metamodel) for metamodel in metamodels
        ],
        "generated_transformation": _cited(_text_artifact(transformation_path)),
        "generated_test": {
            **_cited(generated_test),
            "test_case_ids": generated_test["test_case_ids"],
        },
        "failing_test_case_or_assertion": {
            "test_case_id": None,
            "assertion_id": None,
            "note": (
                "the execution failed before any test method was reported, so "
                "no case and no assertion can be named"
            ),
        },
        "syntax_status": syntax_check,
        "reference_transformation_result": {
            "status": reference_result["status"],
            "assertions_passed": (
                reference_result["observation"]["assertions_passed"]
                if reference_result["observation"] is not None
                else None
            ),
        },
        "generated_execution_summary": {
            "failure_stage": observation.get("failure_stage"),
            "assertions_evaluated": observation.get("assertions_evaluated"),
            "assertions_passed": observation.get("assertions_passed"),
            "error_summary": observation.get("error_summary"),
            "failure_kind": "execution_pair_failure",
            "failure_type": failure["failure_type"],
            "message": failure["message"],
            "expected": None,
            "actual": None,
        },
        "stack_traces": surefire["stack_traces"],
        "system_err": surefire["system_err"],
        "maven_log_excerpt": _relevant_log_lines(execution_log),
    }


def _test_case_ids(semantic_cases_content: str) -> list[str]:
    """Which cases the suite declares — never which of them failed."""
    try:
        payload = json.loads(semantic_cases_content)
    except json.JSONDecodeError as exc:
        raise FailureReportError(f"invalid semantic_cases.json: {exc}") from exc
    tests = payload.get("tests") if isinstance(payload, dict) else None
    if not isinstance(tests, list):
        return []
    return [
        str(test.get("id") or test.get("name") or "")
        for test in tests
        if isinstance(test, dict)
    ]


def write_pair_failure_report(
    request: PairReportRequest, output: Path
) -> dict[str, Any]:
    """Create one immutable pair-level report under ``artifacts/work``."""
    resolved_output = _output_path(output)
    report = build_pair_failure_report(request)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        repository_output = _repository_path(resolved_output)
        raise FailureReportError(
            f"report already exists and is immutable: {repository_output}"
        ) from exc
    return report


def load_report_request(path: Path) -> ReportRequest:
    """Read and validate one repository-contained failure-report request."""
    request_path = _input_path(path, "request")
    try:
        payload = read_json(request_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(
            f"cannot read failure-report request from {request_path}: {exc}"
        ) from exc
    return ReportRequest.from_payload(payload)


def _identity(manifest: dict[str, Any], attempt: int) -> dict[str, Any]:
    # Only the axes the report itself resolves paths from are mandatory. A run
    # may deliberately record a null model axis — that is what `exactly_one`
    # writes when the run fixes no value for it, as an explicitly named
    # transformation does — and refusing the report then would make a whole
    # legitimate run undiagnosable over a provenance field the report only
    # copies. The null is carried through as the null it is.
    required = ("run_id", "task", "language")
    missing = [field for field in required if not isinstance(manifest.get(field), str)]
    if missing:
        raise FailureReportError(
            f"manifest is missing string identity fields: {', '.join(missing)}"
        )
    run_id = str(manifest["run_id"])
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise FailureReportError(f"invalid run_id in manifest: {run_id!r}")
    return {
        "run_id": run_id,
        "task_id": manifest["task"],
        "language": manifest["language"],
        "model": manifest.get("transformation_model"),
        "attempt": attempt,
        "transformation_model": manifest.get("transformation_model"),
        "test_generation_model": manifest.get("test_generation_model"),
        "transformation_strategy": manifest.get("transformation_strategy"),
        "test_generation_strategy": manifest.get("test_generation_strategy"),
    }


def _read_execution(
    path: Path, identity: dict[str, Any], label: str
) -> dict[str, Any]:
    payload = _read_object(path, label)
    expected = {
        "language": identity["language"],
        "task": identity["task_id"],
    }
    mismatches = [
        f"{field}={payload.get(field)!r}, expected {value!r}"
        for field, value in expected.items()
        if payload.get(field) != value
    ]
    if mismatches:
        raise FailureReportError(f"{label} identity mismatch: {'; '.join(mismatches)}")
    _observation(payload, label)
    return payload


def _generated_inputs(execution: dict[str, Any]) -> tuple[Path, Path]:
    inputs = execution.get("inputs")
    if not isinstance(inputs, dict):
        raise FailureReportError("generated execution has no inputs object")
    suite = inputs.get("suite")
    transformation = inputs.get("transformation")
    if not isinstance(suite, dict) or suite.get("role") != "generated_suite":
        raise FailureReportError(
            "generated execution does not identify a generated suite"
        )
    if (
        not isinstance(transformation, dict)
        or transformation.get("role") != "generated_transformation"
    ):
        raise FailureReportError(
            "generated execution does not identify a generated transformation"
        )
    return (
        _input_path(suite.get("path"), "generated suite path", require_file=False),
        _input_path(transformation.get("path"), "transformation path"),
    )


def _verify_recorded_hashes(
    execution: dict[str, Any], suite_dir: Path, transformation_path: Path
) -> None:
    inputs = execution["inputs"]
    recorded_suite_hash = inputs["suite"].get("sha256")
    recorded_transformation_hash = inputs["transformation"].get("sha256")
    actual_suite_hash = directory_sha256(suite_dir)
    actual_transformation_hash = file_sha256(transformation_path)
    if recorded_suite_hash != actual_suite_hash:
        raise FailureReportError(
            "generated suite no longer matches its recorded sha256"
        )
    if recorded_transformation_hash != actual_transformation_hash:
        raise FailureReportError(
            "generated transformation no longer matches its recorded sha256"
        )


def _execution_stage_evidence(
    path: Path,
    generated_execution_path: Path,
    suite_dir: Path,
    transformation_path: Path,
    attempt: int,
    generated_execution: dict[str, Any],
) -> dict[str, Any]:
    """Pin the observation to the requested immutable execution attempt."""
    expected_suffix = (
        "stages",
        "execution",
        "attempts",
        f"attempt-{attempt:03d}",
        "evidence.json",
    )
    if path.parts[-len(expected_suffix) :] != expected_suffix:
        raise FailureReportError(
            "execution_evidence path does not match the requested execution attempt"
        )

    payload = _read_object(path, "execution stage evidence")
    pairs = payload.get("details", {}).get("pairs")
    if not isinstance(pairs, list):
        raise FailureReportError("execution stage evidence has no details.pairs array")
    matching = _matching_execution_pairs(pairs, generated_execution_path)
    if len(matching) != 1:
        raise FailureReportError(
            "execution attempt must reference the generated execution exactly once"
        )

    pair = matching[0]
    pair_suite = _input_path(pair.get("suite"), "pair suite", require_file=False)
    pair_transformation = _input_path(pair.get("transformation"), "pair transformation")
    if pair_suite != suite_dir or pair_transformation != transformation_path:
        raise FailureReportError(
            "execution pair inputs disagree with recorded observation"
        )
    assertions_passed = _observation(
        generated_execution, GENERATED_EXECUTION_LABEL
    )["assertions_passed"]
    if pair.get("assertions_passed") is not assertions_passed:
        raise FailureReportError(
            "execution pair assertion result disagrees with recorded observation"
        )
    return _json_artifact(path)


def _matching_execution_pairs(
    pairs: list[Any], generated_execution_path: Path
) -> list[dict[str, Any]]:
    """Find well-formed pairs that cite the requested execution observation."""
    matching: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        try:
            evidence_path = _input_path(pair.get("evidence"), "pair evidence")
        except FailureReportError:
            continue
        if evidence_path == generated_execution_path:
            matching.append(pair)
    return matching


def _observation(execution: dict[str, Any], label: str) -> dict[str, Any]:
    observation = execution.get("observation")
    if not isinstance(observation, dict):
        raise FailureReportError(f"{label} has no observation object")
    for field in ("assertions_evaluated", "assertions_passed"):
        if not isinstance(observation.get(field), bool):
            raise FailureReportError(f"{label} observation.{field} must be boolean")
    return observation


def _select_test_case(
    semantic_cases: dict[str, Any], test_case_id: str
) -> dict[str, Any]:
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise FailureReportError("semantic_cases.json has no tests array")
    matching = [
        test
        for test in tests
        if isinstance(test, dict)
        and str(test.get("id") or test.get("name") or "") == test_case_id
    ]
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one test case {test_case_id!r}, found {len(matching)}"
        )
    return matching[0]


def _select_assertion(
    test_case: dict[str, Any], assertion_id: str | None
) -> dict[str, Any] | None:
    if assertion_id is None:
        return None
    assertions = test_case.get("assertions")
    if not isinstance(assertions, list):
        raise FailureReportError("selected test case has no assertions array")
    matching: list[dict[str, Any]] = []
    for index, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        recorded_id = str(assertion.get("id") or f"assertion-{index:03d}")
        if recorded_id == assertion_id:
            matching.append({"id": recorded_id, **assertion})
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one assertion {assertion_id!r}, found {len(matching)}"
        )
    return matching[0]


def _syntax_check(evidence: dict[str, Any], transformation: Path) -> dict[str, Any]:
    if isinstance(evidence.get("parsed"), bool):
        diagnostic = evidence.get("diagnostic", "")
        return {
            "status": "passed" if evidence["parsed"] else "failed",
            "parser_diagnostics": _diagnostic_list(diagnostic),
        }

    details = evidence.get("details")
    if not isinstance(details, dict):
        raise FailureReportError("syntax evidence has no details object")
    target = transformation.resolve()
    passed = _resolved_path_set(details.get("passed_transformations", []))
    failed = _resolved_path_set(details.get("failed_transformations", []))
    if target in passed and target in failed:
        raise FailureReportError(
            "transformation is both passed and failed in syntax evidence"
        )
    if target not in passed and target not in failed:
        raise FailureReportError("transformation is absent from syntax evidence")

    selected_diagnostics = _selected_syntax_diagnostics(
        details.get("diagnostics", {}), target, target in failed
    )
    return {
        "status": "passed" if target in passed else "failed",
        "parser_diagnostics": _diagnostic_list(selected_diagnostics),
    }


def _selected_syntax_diagnostics(
    diagnostics: object, target: Path, target_failed: bool
) -> object:
    if not isinstance(diagnostics, dict):
        return diagnostics if target_failed else []
    for raw_path, diagnostic in diagnostics.items():
        try:
            candidate = _input_path(raw_path, "diagnostic path")
        except FailureReportError:
            continue
        if candidate == target:
            return diagnostic
    return []


def _semantic_status(observation: dict[str, Any]) -> str:
    if observation["assertions_evaluated"] is not True:
        return "execution_error"
    return "passed" if observation["assertions_passed"] else "failed"


def _reference_result(
    path: Path | None, identity: dict[str, Any]
) -> dict[str, Any]:
    if path is None:
        return {"status": "not_run", "observation": None, "evidence": None}
    execution = _read_execution(path, identity, "reference execution")
    transformation = execution.get("inputs", {}).get("transformation", {})
    if transformation.get("role") != "reference_transformation":
        raise FailureReportError(
            "reference execution does not identify a reference transformation"
        )
    observation = _observation(execution, "reference execution")
    return {
        "status": "passed" if observation["assertions_passed"] else "failed",
        "observation": observation,
        "evidence": _json_artifact(path),
    }


def _task_description(
    identity: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    path = (
        TARGET.prompt_assets
        / "task_prompts"
        / str(identity["language"])
        / f"{identity['task_id']}.txt"
    )
    artifact = _text_artifact(_input_path(path, "task description"))
    recorded_hash = (
        manifest.get("provenance", {})
        .get("input_hashes", {})
        .get("task_prompt")
    )
    if recorded_hash is not None and artifact["sha256"] != recorded_hash:
        raise FailureReportError(
            "task description no longer matches manifest provenance"
        )
    return artifact


def _metamodel_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    recorded = (
        manifest.get("provenance", {})
        .get("input_hashes", {})
        .get("metamodels")
    )
    if not isinstance(recorded, dict) or not recorded:
        raise FailureReportError("manifest provenance contains no exact metamodels")
    artifacts: list[dict[str, Any]] = []
    for raw_path, expected_hash in sorted(recorded.items()):
        path = _input_path(raw_path, "metamodel path")
        artifact = _text_artifact(path)
        if artifact["sha256"] != expected_hash:
            raise FailureReportError(
                f"metamodel no longer matches manifest provenance: {raw_path}"
            )
        artifacts.append(artifact)
    return artifacts


def _input_models(test_case: dict[str, Any], suite_dir: Path) -> list[dict[str, Any]]:
    models = test_case.get("models", [])
    if not isinstance(models, list):
        raise FailureReportError("test case models must be an array")
    artifacts: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict) or model.get("role") not in {"source", "inout"}:
            continue
        raw_path = model.get("path")
        if raw_path is None:
            continue
        artifacts.append(
            {
                "model": model,
                "artifact": _text_artifact(
                    _suite_artifact_path(suite_dir, raw_path, "input model")
                ),
            }
        )
    return artifacts


def _expected_target_models(
    test_case: dict[str, Any], suite_dir: Path
) -> list[dict[str, Any]]:
    models = test_case.get("models", [])
    if not isinstance(models, list):
        return []
    artifacts: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict) or model.get("role") != "target":
            continue
        raw_path = model.get("path")
        if raw_path is None or model.get("generated") is True:
            continue
        artifacts.append(
            {
                "model": model,
                "artifact": _text_artifact(
                    _suite_artifact_path(suite_dir, raw_path, "expected target model")
                ),
            }
        )
    return artifacts


def _surefire_evidence(
    report_paths: Sequence[Path], test_case_id: str
) -> dict[str, Any]:
    method_name = sanitize_method_name(test_case_id)
    test_cases: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    for path, case in _matching_surefire_cases(report_paths, method_name):
        test_case, exception, trace = _surefire_test_case(path, case)
        test_cases.append(test_case)
        if exception is not None:
            exceptions.append(exception)
        if trace:
            stack_traces.append(trace)
    return {
        "test_cases": test_cases,
        "exceptions": exceptions,
        "stack_traces": stack_traces,
    }


def _matching_surefire_cases(
    report_paths: Sequence[Path], method_name: str
) -> Iterator[tuple[Path, ET.Element]]:
    """Yield matching test cases in report and XML document order."""
    for path in report_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            raise FailureReportError(f"invalid Surefire report {path}: {exc}") from exc
        for case in root.iter("testcase"):
            if case.get("name") == method_name:
                yield path, case


def _surefire_test_case(
    path: Path, case: ET.Element
) -> tuple[dict[str, Any], dict[str, str] | None, str]:
    failure = case.find("failure")
    error = case.find("error")
    node = error if error is not None else failure
    status = (
        "error"
        if error is not None
        else "failed"
        if failure is not None
        else "passed"
    )
    message = str(node.get("message") or "") if node is not None else ""
    expected, actual = _assertion_outcome(message)
    test_case = {
        "report": _repository_path(path),
        "test_class": case.get("classname"),
        "test_method": case.get("name"),
        "duration_seconds": case.get("time"),
        "status": status,
        "failure_type": (
            str(node.get("type") or node.tag) if node is not None else None
        ),
        "message": message or None,
        "expected": expected,
        "actual": actual,
    }
    if node is None:
        return test_case, None, ""
    exception = {
        "type": str(node.get("type") or node.tag),
        "message": message,
    }
    return test_case, exception, (node.text or "").strip()


def _assertion_outcome(message: str) -> tuple[str | None, str | None]:
    """The expected and actual values JUnit printed, or ``(None, None)``.

    Extraction is deliberately literal. When the message is not exactly the
    ``expected: <X> but was: <Y>`` shape the pair is unknown, and an unknown
    actual result is reported as unknown: the raw message and the archived
    report stay in the evidence, and the diagnosis LLM is never handed a value
    this module reconstructed.
    """
    prefix_at = message.find(ASSERTION_OUTCOME_PREFIX)
    separator_at = message.rfind(ASSERTION_OUTCOME_SEPARATOR)
    if prefix_at < 0 or separator_at < prefix_at or not message.rstrip().endswith(">"):
        return None, None
    expected = message[prefix_at + len(ASSERTION_OUTCOME_PREFIX) : separator_at]
    if not expected.endswith(">"):
        return None, None
    actual = message.rstrip()[separator_at + len(ASSERTION_OUTCOME_SEPARATOR) : -1]
    return expected[:-1], actual


def _recorded_failure_view(surefire_evidence: dict[str, Any]) -> dict[str, Any] | None:
    """The one recorded failure this report is about, if there is one.

    Both JUnit outcomes qualify and are kept apart by ``kind``: a ``failure`` is
    an assertion that was evaluated and did not hold, an ``error`` is a throw
    before any verdict. The second is still a real failure of the pairing — it
    is what a broken generated transformation usually produces — so it gets a
    report, with the exception and stack trace as its evidence and no invented
    expected/actual.

    ``None`` when the reports name no failure for the selected test method, or
    name more than one: neither state identifies a single failure, and picking
    one would be a choice this module has no evidence for.
    """
    failures = [
        case
        for case in surefire_evidence["test_cases"]
        if case.get("status") in {"failed", "error"}
    ]
    if len(failures) != 1:
        return None
    failure = failures[0]
    return {
        "kind": (
            "assertion_failure"
            if failure.get("status") == "failed"
            else "runtime_error"
        ),
        "report": failure.get("report"),
        "test_class": failure.get("test_class"),
        "test_method": failure.get("test_method"),
        "failure_type": failure.get("failure_type"),
        "message": failure.get("message"),
        "expected": failure.get("expected"),
        "actual": failure.get("actual"),
        "extraction": (
            "junit_assertion_message"
            if failure.get("expected") is not None or failure.get("actual") is not None
            else "unavailable"
        ),
    }


def _require_concrete_assertion_failure(
    test_case: dict[str, Any],
    assertion: dict[str, Any],
    surefire_evidence: dict[str, Any],
) -> None:
    """Prove that the selected case and assertion are the recorded failure."""
    failed_cases = [
        case
        for case in surefire_evidence["test_cases"]
        if case.get("status") == "failed"
    ]
    if len(failed_cases) != 1:
        raise FailureReportError(
            "diagnosis-eligible report requires exactly one matching Surefire "
            f"assertion failure, found {len(failed_cases)}"
        )

    selected_message = _assertion_message(assertion)
    assertion_messages = [
        _assertion_message(candidate)
        for candidate in test_case.get("assertions", [])
        if isinstance(candidate, dict)
    ]
    if assertion_messages.count(selected_message) != 1:
        raise FailureReportError(
            "selected assertion message is not unique within the test case"
        )
    recorded_failure = "\n".join(
        [
            *(
                str(exception.get("message", ""))
                for exception in surefire_evidence["exceptions"]
            ),
            *(str(trace) for trace in surefire_evidence["stack_traces"]),
        ]
    )
    if selected_message not in recorded_failure:
        raise FailureReportError(
            "selected assertion_id does not match the Surefire failure message"
        )


def _assertion_message(assertion: dict[str, Any]) -> str:
    explicit = assertion.get("message")
    if isinstance(explicit, str) and explicit:
        return explicit
    required = ("kind", "model", "type")
    if not all(field in assertion for field in required):
        raise FailureReportError(
            "assertion needs an explicit message or kind/model/type identity"
        )
    return (
        f"{assertion['kind']} assertion for "
        f"{assertion['model']}::{assertion['type']}"
    )


def _diagnosis_reason(
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
    *,
    input_models: list[dict[str, Any]],
    observed_failure_evidence: dict[str, Any],
) -> str:
    """Why this failure is or is not a case Source Diagnosis may be asked about.

    Four conditions, in the order the pipeline establishes them:

    1. the generated transformation is syntactically valid;
    2. the suite was validated against the reference transformation;
    3. a real failure of the pairing was observed on the generated one;
    4. enough execution evidence survived to say what happened.

    Note what is *not* a condition: that an assertion was evaluated. A validated
    test that throws on a generated transformation has failed against it, and
    that failure is exactly what Source Diagnosis exists to attribute — to the
    transformation, to the test, or to neither. Requiring a JUnit assertion
    failure would silently exclude the most common shape of a transformation
    defect.

    A timeout or an infrastructure failure is excluded instead, because neither
    is evidence about the pairing at all.

    Missing evidence downgrades eligibility rather than aborting: the report is
    still the run's record of a real failure, and saying why it cannot be
    diagnosed is more useful than refusing to write it.
    """
    if syntax_check["status"] != "passed":
        return "transformation_parser_check_failed"
    if observation["assertions_passed"] is True:
        return "semantic_test_passed"
    if observation.get("timed_out") is True or observation.get("failure_stage") in {
        "timeout",
        "infrastructure",
    }:
        return "failure_not_attributable_to_the_pairing"
    if reference_result.get("status") != "passed":
        return "reference_result_not_passing"
    if not input_models:
        return "no_recorded_input_model"
    if not any(
        observed_failure_evidence[fact]
        for fact in (
            "target_model_snapshots",
            "assertion_expected_actual",
            "structured_difference",
            "recorded_exception",
        )
    ):
        return "no_observed_failure_evidence"
    return "parser_passed_and_semantic_test_failed"


def _validate_difference(value: object) -> dict[str, list[Any]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FailureReportError("actual_vs_expected must be an object or null")
    missing = [field for field in DIFF_FIELDS if field not in value]
    unknown = sorted(set(value) - set(DIFF_FIELDS))
    if missing or unknown:
        problems = []
        if missing:
            problems.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown fields: {', '.join(unknown)}")
        raise FailureReportError(f"invalid actual_vs_expected: {'; '.join(problems)}")
    normalized: dict[str, list[Any]] = {}
    for field in DIFF_FIELDS:
        entries = value[field]
        if not isinstance(entries, list):
            raise FailureReportError(f"actual_vs_expected.{field} must be an array")
        normalized[field] = entries
    return normalized


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(f"cannot read {label} from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FailureReportError(f"{label} must contain one JSON object")
    return payload


def _log_excerpt(path: Path) -> dict[str, Any]:
    """A bounded, self-describing citation of one build log.

    The excerpt is the log's own tail, verbatim; ``path`` and ``sha256`` name the
    complete stream so a reader who needs the rest can always get it, and
    ``truncated`` says outright that this is not the whole file.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FailureReportError(f"cannot read evidence file {path}: {exc}") from exc
    lines = content.splitlines()
    excerpt = "\n".join(lines[-EXECUTION_LOG_EXCERPT_LINES:])
    if len(excerpt) > EXECUTION_LOG_EXCERPT_CHARS:
        excerpt = excerpt[-EXECUTION_LOG_EXCERPT_CHARS:]
    return {
        "path": _repository_path(path),
        "sha256": file_sha256(path),
        "lines": len(lines),
        "excerpt": excerpt,
        "excerpt_lines": excerpt.count("\n") + 1 if excerpt else 0,
        "truncated": excerpt != content.rstrip("\n"),
    }


def _text_artifact(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FailureReportError(
            f"cannot read UTF-8 evidence file {path}: {exc}"
        ) from exc
    return {
        "path": _repository_path(path),
        "sha256": file_sha256(path),
        "content": content,
    }


def _json_artifact(path: Path) -> dict[str, Any]:
    artifact = _text_artifact(path)
    try:
        artifact["document"] = json.loads(artifact["content"])
    except json.JSONDecodeError as exc:
        raise FailureReportError(f"invalid JSON evidence file {path}: {exc}") from exc
    return artifact


def _suite_artifact_path(suite_dir: Path, raw_path: object, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise FailureReportError(f"{label} path must be a non-empty string")
    candidate = (suite_dir / raw_path).resolve()
    try:
        candidate.relative_to(suite_dir.resolve())
    except ValueError as exc:
        raise FailureReportError(
            f"{label} escapes the generated suite: {raw_path}"
        ) from exc
    if not candidate.is_file():
        raise FailureReportError(f"{label} does not exist: {raw_path}")
    return candidate


def _input_path(
    value: object, label: str, *, require_file: bool = True
) -> Path:
    if isinstance(value, Path):
        candidate = value
    elif isinstance(value, str) and value:
        candidate = Path(value)
    else:
        raise FailureReportError(f"{label} must be a non-empty path string")
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (REPO_ROOT / candidate).resolve()
    )
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise FailureReportError(
            f"{label} escapes the repository: {candidate}"
        ) from exc
    if require_file and not resolved.is_file():
        raise FailureReportError(f"{label} is not a file: {candidate}")
    if not require_file and not resolved.is_dir():
        raise FailureReportError(f"{label} is not a directory: {candidate}")
    return resolved


def _optional_input_path(value: object, label: str) -> Path | None:
    return None if value is None else _input_path(value, label)


def _input_paths(value: object, label: str) -> tuple[Path, ...]:
    if not isinstance(value, list):
        raise FailureReportError(f"{label} must be an array of paths")
    return tuple(
        _input_path(path, f"{label}[{index}]")
        for index, path in enumerate(value)
    )


def _output_path(value: Path) -> Path:
    candidate = value if value.is_absolute() else REPO_ROOT / value
    resolved = candidate.resolve()
    try:
        resolved.relative_to(TARGET.artifacts_work.resolve())
    except ValueError as exc:
        raise FailureReportError("output must stay under artifacts/work") from exc
    return resolved


def _repository_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise FailureReportError(f"path escapes the repository: {path}") from exc


def _request_payload(
    payload: object,
    allowed_fields: frozenset[str],
) -> dict[str, Any]:
    """Validate the common JSON-object boundary for report requests."""
    if not isinstance(payload, dict):
        raise FailureReportError("request must be one JSON object")
    unknown_fields = sorted(set(payload) - allowed_fields)
    if unknown_fields:
        raise FailureReportError(
            f"request contains unknown fields: {', '.join(unknown_fields)}"
        )
    return payload


def _positive_attempt(payload: dict[str, Any]) -> int:
    """Return a validated one-based execution-attempt number."""
    attempt = payload.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise FailureReportError("attempt must be a positive integer")
    return attempt


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FailureReportError(f"{field} must be a non-empty string")
    return value


def _resolved_path_set(value: object) -> set[Path]:
    if not isinstance(value, list):
        raise FailureReportError("syntax transformation list must be an array")
    resolved: set[Path] = set()
    for index, raw_path in enumerate(value):
        resolved.add(_input_path(raw_path, f"syntax transformation[{index}]").resolve())
    return resolved


def _diagnostic_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(entry) for entry in value if str(entry).strip()]
    if isinstance(value, dict):
        return [f"{key}: {entry}" for key, entry in sorted(value.items())]
    return [str(value)]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble one immutable per-assertion semantic failure report."
    )
    parser.add_argument("--request", type=Path, required=True, help="JSON request file")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new report path below artifacts/work",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns non-zero without writing a partial report."""
    args = _parse_args(argv)
    try:
        request = load_report_request(args.request)
        write_failure_report(request, args.output)
    except (FailureReportError, FileExistsError, json.JSONDecodeError, OSError) as exc:
        print(f"failure report error: {exc}", file=sys.stderr)
        return 2
    print(_repository_path(_output_path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
