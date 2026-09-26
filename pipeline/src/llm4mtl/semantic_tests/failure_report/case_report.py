"""The report about one test case, and where a report may name an assertion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.semantic_tests.codegen.java_rendering import assertion_message
from llm4mtl.semantic_tests.failure_report.artifacts import (
    _cited,
    _optional_log_excerpt,
    _read_object,
    _relevant_log_lines,
    _suite_artifact_path,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.eligibility import (
    CASE_ELIGIBLE_REASON,
    _diagnosis_reason,
)
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.evidence import (
    RecordedExecution,
    ReportContext,
    resolve_recorded_execution,
    resolve_report_context,
)
from llm4mtl.semantic_tests.failure_report.models import (
    ASSERTION_FAILURE_KIND,
    CASE_REPORT_TYPE,
    DIFF_FIELDS,
    JUNIT_MESSAGE_EXTRACTION,
    RUNTIME_ERROR_KIND,
)
from llm4mtl.semantic_tests.failure_report.report_document import (
    REQUIRED_RESULT_FIELDS,
    bundle_head,
    execution_section,
    execution_summary,
    persist_once,
    recorded_error_summary,
    reference_verdict,
    report_document,
    source_diagnosis_section,
    versions_section,
)
from llm4mtl.semantic_tests.failure_report.request import ReportRequest, _output_path
from llm4mtl.semantic_tests.failure_report.semantic_cases import (
    assertion_id,
    case_id,
    rendered_method_name,
)
from llm4mtl.semantic_tests.failure_report.surefire_view import (
    _recorded_failure_view,
    _surefire_evidence,
)
from llm4mtl.semantic_tests.semantic_spec import SEMANTIC_CASES_FILE

# A per-case diagnosis must also name the case it is about.
CASE_RESULT_FIELDS = (*REQUIRED_RESULT_FIELDS, "test_case_id")


def write_failure_report(request: ReportRequest, output: Path) -> dict[str, Any]:
    """Create one immutable report under ``artifacts/work`` and return it."""
    resolved_output = _output_path(output)
    report = build_failure_report(request)
    persist_once(report, resolved_output)
    return report


def build_failure_report(request: ReportRequest) -> dict[str, Any]:
    """Build a self-contained report for one recorded failure.

    Diagnosis eligibility is derived from recorded facts only — the parser
    verdict, the reference result, the generated-transformation observation, and
    what evidence survived.  See :func:`_diagnosis_reason` for the conditions.
    """
    recorded = resolve_recorded_execution(request)
    test_case, assertion = _selected_case_and_assertion(request, recorded.suite_dir)
    context = resolve_report_context(request, recorded)
    result = _test_case_result(request, recorded, context, test_case, assertion)
    reason = _diagnosis_reason(
        context.syntax_check,
        context.observation,
        context.reference_result,
        input_models=result["input_model"]["models"],
        observed_failure_evidence=result["observed_failure_evidence"],
    )
    is_eligible = reason == CASE_ELIGIBLE_REASON
    if is_eligible and _claims_one_assertion(result):
        _require_concrete_assertion_failure(result)
    evidence_bundle = (
        _evidence_bundle(context, recorded.transformation_path, result)
        if is_eligible
        else None
    )
    return report_document(
        report_type=CASE_REPORT_TYPE,
        recorded=recorded,
        context=context,
        body_key="test_case_result",
        body=result,
        source_diagnosis=source_diagnosis_section(
            is_eligible=is_eligible,
            reason=reason,
            evidence_bundle=evidence_bundle,
            required_result_fields=CASE_RESULT_FIELDS,
        ),
    )


def _selected_case_and_assertion(
    request: ReportRequest, suite_dir: Path
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    semantic_cases = _read_object(suite_dir / SEMANTIC_CASES_FILE, "semantic cases")
    test_case = _select_test_case(semantic_cases, request.test_case_id)
    return test_case, _select_assertion(test_case, request.assertion_id)


def _test_case_result(
    request: ReportRequest,
    recorded: RecordedExecution,
    context: ReportContext,
    test_case: dict[str, Any],
    assertion: dict[str, Any] | None,
) -> dict[str, Any]:
    """The ``test_case_result`` body: the case, what the run observed, versions."""
    models = _model_sections(request, test_case, assertion, recorded.suite_dir)
    surefire_evidence = _surefire_evidence(
        request.surefire_reports, rendered_method_name(test_case)
    )
    failure = _recorded_failure_view(surefire_evidence)
    return {
        "test_case_id": request.test_case_id,
        "assertion_id": request.assertion_id,
        "semantic_status": context.semantic_status,
        "syntax_check": context.syntax_check,
        "test_case": test_case,
        "assertion": assertion,
        **models,
        "actual_vs_expected": _difference(request.actual_vs_expected),
        "failure": failure,
        "observed_failure_evidence": _observed_failure_evidence(
            request, models["actual_target_model"], failure, surefire_evidence
        ),
        "execution": execution_section(
            context,
            recorded,
            _execution_error(context.observation, surefire_evidence, request),
        ),
        "reference_transformation_result": context.reference_result,
        "versions": versions_section(recorded),
    }


def _model_sections(
    request: ReportRequest,
    test_case: dict[str, Any],
    assertion: dict[str, Any] | None,
    suite_dir: Path,
) -> dict[str, Any]:
    """The input models, the expected output, and the actual target models."""
    return {
        "input_model": {
            "models": _input_models(test_case, suite_dir),
            "changes": test_case.get("changes", []),
        },
        "expected_output_or_properties": {
            "assertion": assertion,
            "target_models": _expected_target_models(test_case, suite_dir),
        },
        "actual_target_model": [
            _text_artifact(path) for path in request.actual_target_models
        ],
    }


def _difference(actual_vs_expected: dict[str, list[Any]] | None) -> dict[str, Any]:
    """The comparator difference, or an explicit statement that there is none."""
    if actual_vs_expected is None:
        return {"available": False, **{field: None for field in DIFF_FIELDS}}
    return {"available": True, **actual_vs_expected}


def _observed_failure_evidence(
    request: ReportRequest,
    actual_target_models: list[dict[str, Any]],
    failure: dict[str, Any] | None,
    surefire_evidence: dict[str, Any],
) -> dict[str, Any]:
    """What the run observed about this failure, as separate facts.

    Diagnosis needs at least one of them; without any, the LLM would know
    nothing about what happened. A runtime throw counts too: an exception with
    its stack trace is evidence, and it is what a transformation defect most
    often produces.
    """
    return {
        "target_model_snapshots": len(actual_target_models),
        "assertion_expected_actual": failure is not None
        and failure["extraction"] == JUNIT_MESSAGE_EXTRACTION,
        "structured_difference": request.actual_vs_expected is not None,
        "recorded_exception": bool(surefire_evidence["exceptions"]),
    }


def _execution_error(
    observation: dict[str, Any],
    surefire_evidence: dict[str, Any],
    request: ReportRequest,
) -> dict[str, Any]:
    return {
        "error_summary": recorded_error_summary(observation),
        "exceptions": surefire_evidence["exceptions"],
        "stack_traces": surefire_evidence["stack_traces"],
        "execution_log": _optional_log_excerpt(request.execution_log),
        "surefire": surefire_evidence["test_cases"],
    }


def _claims_one_assertion(result: dict[str, Any]) -> bool:
    """Only an assertion failure claims to be about one assertion.

    So only such a report has to prove that the selected assertion is the one
    that lost.
    """
    failure = result["failure"]
    return (
        result["assertion"] is not None
        and failure is not None
        and failure["kind"] == ASSERTION_FAILURE_KIND
    )


def _evidence_bundle(
    context: ReportContext, transformation_path: Path, result: dict[str, Any]
) -> dict[str, Any]:
    """The part of the report a diagnosis prompt reads.

    The stored report keeps everything the run recorded. The bundle carries each
    fact once, in the form a reader needs: contents without hashes, the
    reference result as a verdict, a summary of what failed, and a short
    build-log excerpt. The whole report would fill the prompt with provenance
    the LLM cannot use.
    """
    execution = result["execution"]
    failure_summary, runtime_stack_traces = _failure_evidence(
        result["failure"], execution["error"]["stack_traces"]
    )
    return {
        **bundle_head(context, transformation_path),
        "failing_test_case_or_assertion": _failing_case_and_assertion(result),
        "input_model": _cited_input_models(result),
        "changes": result["input_model"]["changes"],
        "expected_output_or_properties": result["expected_output_or_properties"],
        "syntax_status": result["syntax_check"],
        "reference_transformation_result": reference_verdict(
            result["reference_transformation_result"]
        ),
        "generated_execution_summary": {
            **execution_summary(execution["observation"]),
            **failure_summary,
        },
        "actual_target_model": [
            _cited(model) for model in result["actual_target_model"]
        ],
        "structured_actual_vs_expected_difference": result["actual_vs_expected"],
        # A runtime failure keeps its stack trace: it shows where the throw came
        # from. An assertion failure drops it: the message already holds the
        # mismatch, and the trace only shows harness code.
        "stack_traces": runtime_stack_traces,
        "maven_log_excerpt": _relevant_log_lines(execution["error"]["execution_log"]),
    }


def _cited_input_models(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"model": entry["model"], **_cited(entry["artifact"])}
        for entry in result["input_model"]["models"]
    ]


def _failing_case_and_assertion(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_case_id": result["test_case_id"],
        "assertion_id": result["assertion_id"],
        "test_case": result["test_case"],
        "assertion": result["assertion"],
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
    return summary, stack_traces if failure["kind"] == RUNTIME_ERROR_KIND else []


def _select_test_case(
    semantic_cases: dict[str, Any], test_case_id: str
) -> dict[str, Any]:
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise FailureReportError(f"{SEMANTIC_CASES_FILE} has no tests array")
    matching = [
        test
        for test in tests
        if isinstance(test, dict) and case_id(test) == test_case_id
    ]
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one test case {test_case_id!r}, found {len(matching)}"
        )
    return matching[0]


def _select_assertion(
    test_case: dict[str, Any], selected_id: str | None
) -> dict[str, Any] | None:
    if selected_id is None:
        return None
    assertions = test_case.get("assertions")
    if not isinstance(assertions, list):
        raise FailureReportError("selected test case has no assertions array")
    matching: list[dict[str, Any]] = []
    for position, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        recorded_id = assertion_id(assertion, position)
        if recorded_id == selected_id:
            matching.append({"id": recorded_id, **assertion})
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one assertion {selected_id!r}, found {len(matching)}"
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
    """The expected target models; :func:`_input_models` checked ``models``."""
    models = test_case.get("models", [])
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


def _require_concrete_assertion_failure(result: dict[str, Any]) -> None:
    """Prove that the selected assertion is the one the recorded failure lost.

    The failure view already holds exactly one failed test method for the
    case, so what is left to prove is the assertion.
    """
    error = result["execution"]["error"]
    selected_message = _unique_assertion_message(
        result["test_case"], result["assertion"]
    )
    if selected_message not in _recorded_failure_text(error):
        raise FailureReportError(
            "selected assertion_id does not match the Surefire failure message"
        )


def _unique_assertion_message(
    test_case: dict[str, Any], assertion: dict[str, Any]
) -> str:
    """The selected assertion's message, refused when another one prints it too."""
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
    return selected_message


def _recorded_failure_text(error: dict[str, Any]) -> str:
    """Every recorded exception message and stack trace, one per line."""
    return "\n".join(
        [
            *(str(exception.get("message", "")) for exception in error["exceptions"]),
            *(str(trace) for trace in error["stack_traces"]),
        ]
    )


def _assertion_message(assertion: dict[str, Any]) -> str:
    """The harness message for ``assertion``, refusing an unnameable one.

    The rule is the renderer's own, so a report never looks for a message the
    harness could not have printed. This adds the refusal: an assertion with
    neither a message nor kind/model/type has no message, and matching a
    failure against nothing would be a blind guess.
    """
    message = assertion_message(assertion)
    if not message:
        raise FailureReportError(
            "assertion needs an explicit message or kind/model/type identity"
        )
    return message
