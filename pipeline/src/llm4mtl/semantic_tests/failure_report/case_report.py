"""The report about one test case, and where a report may name an assertion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.semantic_tests.codegen.java_rendering import assertion_message
from llm4mtl.semantic_tests.failure_report.artifacts import (
    _cited,
    _log_excerpt,
    _read_object,
    _relevant_log_lines,
    _repository_path,
    _suite_artifact_path,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.eligibility import _diagnosis_reason
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.evidence import (
    resolve_recorded_execution,
    resolve_report_context,
)
from llm4mtl.semantic_tests.failure_report.models import (
    CASE_REPORT_TYPE,
    DIFF_FIELDS,
    SCHEMA_VERSION,
)
from llm4mtl.semantic_tests.failure_report.request import ReportRequest, _output_path
from llm4mtl.semantic_tests.failure_report.surefire_view import (
    _recorded_failure_view,
    _surefire_evidence,
)
from llm4mtl.serialization.hashing import directory_sha256, file_sha256
from llm4mtl.serialization.json_io import write_json_once


def build_failure_report(request: ReportRequest) -> dict[str, Any]:
    """Build a self-contained report for one recorded failure.

    Diagnosis eligibility is derived from recorded facts only — the parser
    verdict, the reference result, the generated-transformation observation, and
    what evidence survived.  See :func:`_diagnosis_reason` for the conditions.
    """
    recorded = resolve_recorded_execution(request)
    manifest = recorded.manifest
    identity = recorded.identity
    generated_execution = recorded.generated_execution
    suite_dir = recorded.suite_dir
    transformation_path = recorded.transformation_path
    execution_stage_evidence = recorded.stage_evidence

    semantic_cases_path = suite_dir / "semantic_cases.json"
    semantic_cases = _read_object(semantic_cases_path, "semantic cases")
    test_case = _select_test_case(semantic_cases, request.test_case_id)
    assertion = _select_assertion(test_case, request.assertion_id)

    context = resolve_report_context(request, recorded)
    syntax_check = context.syntax_check
    observation = context.observation
    semantic_status = context.semantic_status
    reference_result = context.reference_result
    task_description = context.task_description
    metamodels = context.metamodels
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

    versions = {
        "generated_transformation": {
            "sha256": file_sha256(transformation_path),
            "path": _repository_path(transformation_path),
        },
        "generated_test": {
            "sha256": directory_sha256(suite_dir),
            "path": _repository_path(suite_dir),
            "renderer_version": manifest.get("provenance", {}).get("renderer_version"),
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
    reference_observation = reference_result["observation"]
    reference_assertions_passed = (
        reference_observation["assertions_passed"]
        if reference_observation is not None
        else None
    )
    failure_summary, runtime_stack_traces = _failure_evidence(
        failure,
        surefire_evidence["stack_traces"],
    )
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
            "assertions_passed": reference_assertions_passed,
        },
        "generated_execution_summary": {
            "failure_stage": observation.get("failure_stage"),
            "assertions_evaluated": observation.get("assertions_evaluated"),
            "assertions_passed": observation.get("assertions_passed"),
            "error_summary": observation.get("error_summary"),
            **failure_summary,
        },
        "actual_target_model": [_cited(model) for model in actual_target_models],
        "structured_actual_vs_expected_difference": difference,
        # A stack trace is what identifies where a throw came from, so a runtime
        # failure keeps it. An assertion failure does not need it: its message
        # already carries the mismatch, and the trace is harness plumbing.
        "stack_traces": runtime_stack_traces,
        "maven_log_excerpt": _relevant_log_lines(
            test_case_result["execution"]["error"]["execution_log"]
        ),
    }


def _failure_evidence(
    failure: dict[str, Any] | None,
    stack_traces: list[str],
) -> tuple[dict[str, Any], list[str]]:
    if not failure:
        return {
            "failure_kind": None,
            "failure_type": None,
            "message": None,
            "expected": None,
            "actual": None,
        }, []
    summary = {
        "failure_kind": failure["kind"],
        "failure_type": failure["failure_type"],
        "message": failure["message"],
        "expected": failure["expected"],
        "actual": failure["actual"],
    }
    return summary, stack_traces if failure["kind"] == "runtime_error" else []


def write_failure_report(request: ReportRequest, output: Path) -> dict[str, Any]:
    """Create one immutable report under ``artifacts/work`` and return it."""
    resolved_output = _output_path(output)
    report = build_failure_report(request)
    validate_artifact("failure-report", report)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        repository_output = _repository_path(resolved_output)
        raise FailureReportError(
            f"report already exists and is immutable: {repository_output}"
        ) from exc
    return report


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
    """The harness message for ``assertion``, refusing an unnameable one.

    The rule is the renderer's own, so a report cannot look for a message the
    harness would never have printed. What this adds is the refusal: an
    assertion with neither a message nor kind/model/type identity yields no
    message at all, and matching a recorded failure against nothing would
    attribute it blindly.
    """
    message = assertion_message(assertion)
    if not message:
        raise FailureReportError(
            "assertion needs an explicit message or kind/model/type identity"
        )
    return message
