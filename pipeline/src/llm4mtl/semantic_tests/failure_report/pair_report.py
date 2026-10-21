"""The report about one suite/transformation execution as a whole."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.semantic_tests.failure_report.artifacts import (
    _cited,
    _optional_log_excerpt,
    _relevant_log_lines,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.eligibility import (
    PAIR_ELIGIBLE_REASON,
    _pair_diagnosis_reason,
)
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.evidence import (
    RecordedExecution,
    ReportContext,
    resolve_recorded_execution,
    resolve_report_context,
)
from llm4mtl.semantic_tests.failure_report.models import (
    NO_EXTRACTION,
    PAIR_FAILURE_KIND,
    PAIR_REPORT_TYPE,
    PAIR_SCOPE,
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
from llm4mtl.semantic_tests.failure_report.request import PairReportRequest, _output_path
from llm4mtl.semantic_tests.failure_report.semantic_cases import case_id
from llm4mtl.semantic_tests.failure_report.surefire_view import _pair_surefire_evidence
from llm4mtl.semantic_tests.semantic_spec import SEMANTIC_CASES_FILE

NO_CASE_NOTE = (
    "the execution failed before any test method was reported, so "
    "no case and no assertion can be named"
)


def write_pair_failure_report(
    request: PairReportRequest, output: Path
) -> dict[str, Any]:
    """Create one immutable pair-level report under ``artifacts/work``."""
    resolved_output = _output_path(output)
    report = build_pair_failure_report(request)
    persist_once(report, resolved_output)
    return report


def build_pair_failure_report(request: PairReportRequest) -> dict[str, Any]:
    """Build a report about one suite/transformation execution as a whole.

    This is the report for a failure the run could not attribute to any test
    method, for example when the engine refused the transformation or the
    harness died before Surefire wrote a per-test entry. It is still a real
    failure of a reference-validated suite against a generated transformation,
    so the evidence that exists is collected and nothing else is added.

    Nothing is guessed. ``test_case_id``, ``assertion_id``, ``expected`` and
    ``actual`` are null, and the whole generated test is given instead of one
    case, because the run did not record which case failed.
    """
    recorded = resolve_recorded_execution(request)
    context = resolve_report_context(request, recorded)
    surefire = _pair_surefire_evidence(request.surefire_reports)
    execution_log = _optional_log_excerpt(request.execution_log)
    result = _pair_result(recorded, context, surefire, execution_log)
    reason = _pair_reason(context, surefire, execution_log, result)
    is_eligible = reason == PAIR_ELIGIBLE_REASON
    evidence_bundle = (
        _pair_evidence_bundle(context, recorded.transformation_path, result)
        if is_eligible
        else None
    )
    return report_document(
        report_type=PAIR_REPORT_TYPE,
        recorded=recorded,
        context=context,
        body_key="pair_result",
        body=result,
        source_diagnosis=source_diagnosis_section(
            is_eligible=is_eligible,
            reason=reason,
            evidence_bundle=evidence_bundle,
            required_result_fields=REQUIRED_RESULT_FIELDS,
        ),
    )


def _pair_reason(
    context: ReportContext,
    surefire: dict[str, Any],
    execution_log: dict[str, Any] | None,
    result: dict[str, Any],
) -> str:
    return _pair_diagnosis_reason(
        context.syntax_check,
        context.observation,
        context.reference_result,
        execution_attempted=execution_log is not None or bool(surefire["reports"]),
        per_test_failures=surefire["test_failures"],
        preserved_failure_evidence=result["preserved_failure_evidence"],
    )


def _pair_result(
    recorded: RecordedExecution,
    context: ReportContext,
    surefire: dict[str, Any],
    execution_log: dict[str, Any] | None,
) -> dict[str, Any]:
    """The ``pair_result`` body: the whole test, the failure, and versions."""
    observation = context.observation
    generated_test = _text_artifact(recorded.suite_dir / SEMANTIC_CASES_FILE)
    return {
        # Null, not omitted: a reader must see that this failure has no case
        # and no assertion, not wonder whether the fields were dropped.
        "test_case_id": None,
        "assertion_id": None,
        "semantic_status": context.semantic_status,
        "syntax_check": context.syntax_check,
        "generated_test": {
            **generated_test,
            "suite_id": recorded.generated_execution.get("suite_id"),
            "test_case_ids": _test_case_ids(generated_test["content"]),
        },
        "generated_transformation": _text_artifact(recorded.transformation_path),
        "failure": _pair_failure(observation, surefire),
        "preserved_failure_evidence": _preserved_failure_evidence(
            observation, surefire, execution_log
        ),
        "execution": execution_section(
            context,
            recorded,
            _pair_execution_error(observation, surefire, execution_log),
        ),
        "reference_transformation_result": context.reference_result,
        "versions": versions_section(recorded),
    }


def _pair_failure(
    observation: dict[str, Any], surefire: dict[str, Any]
) -> dict[str, Any]:
    return {
        "scope": PAIR_SCOPE,
        "failure_stage": observation.get("failure_stage"),
        "failure_type": surefire["failure_type"],
        "message": surefire["message"] or recorded_error_summary(observation),
        # A failure that reached no assertion produced no expected and no
        # actual. Both stay null; the harness never computed either.
        "expected": None,
        "actual": None,
        "extraction": NO_EXTRACTION,
    }


def _preserved_failure_evidence(
    observation: dict[str, Any],
    surefire: dict[str, Any],
    execution_log: dict[str, Any] | None,
) -> dict[str, bool]:
    return {
        "recorded_exception": bool(surefire["exceptions"]),
        "system_err": bool(surefire["system_err"]),
        "error_summary": bool(recorded_error_summary(observation).strip()),
        "maven_log": execution_log is not None,
    }


def _pair_execution_error(
    observation: dict[str, Any],
    surefire: dict[str, Any],
    execution_log: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "error_summary": recorded_error_summary(observation),
        "exceptions": surefire["exceptions"],
        "stack_traces": surefire["stack_traces"],
        "system_err": surefire["system_err"],
        "execution_log": execution_log,
        "surefire_reports": surefire["reports"],
    }


def _pair_evidence_bundle(
    context: ReportContext, transformation_path: Path, result: dict[str, Any]
) -> dict[str, Any]:
    """The prompt-shaped subset of a pair-level report.

    It answers the same question as the per-case bundle with less: the task,
    the transformation and the test, that the test passed on the reference, and
    how the execution died. It must not suggest a failing case the run never
    identified.
    """
    generated_test = result["generated_test"]
    failure = result["failure"]
    execution = result["execution"]
    return {
        **bundle_head(context, transformation_path),
        "generated_test": {
            **_cited(generated_test),
            "test_case_ids": generated_test["test_case_ids"],
        },
        "failing_test_case_or_assertion": {
            "test_case_id": None,
            "assertion_id": None,
            "note": NO_CASE_NOTE,
        },
        "syntax_status": result["syntax_check"],
        "reference_transformation_result": reference_verdict(
            result["reference_transformation_result"]
        ),
        "generated_execution_summary": {
            **execution_summary(execution["observation"]),
            "failure_kind": PAIR_FAILURE_KIND,
            "failure_type": failure["failure_type"],
            "message": failure["message"],
            "expected": None,
            "actual": None,
        },
        "stack_traces": execution["error"]["stack_traces"],
        "system_err": execution["error"]["system_err"],
        "maven_log_excerpt": _relevant_log_lines(execution["error"]["execution_log"]),
    }


def _test_case_ids(semantic_cases_content: str) -> list[str]:
    """Which cases the suite declares — never which of them failed."""
    try:
        payload = json.loads(semantic_cases_content)
    except json.JSONDecodeError as exc:
        raise FailureReportError(f"invalid {SEMANTIC_CASES_FILE}: {exc}") from exc
    tests = payload.get("tests") if isinstance(payload, dict) else None
    if not isinstance(tests, list):
        return []
    return [case_id(test) for test in tests if isinstance(test, dict)]

