"""The report about one suite/transformation execution as a whole."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.semantic_tests.failure_report.artifacts import (
    _cited,
    _log_excerpt,
    _relevant_log_lines,
    _repository_path,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.eligibility import _pair_diagnosis_reason
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.evidence import (
    resolve_recorded_execution,
    resolve_report_context,
)
from llm4mtl.semantic_tests.failure_report.models import (
    PAIR_REPORT_TYPE,
    SCHEMA_VERSION,
)
from llm4mtl.semantic_tests.failure_report.request import PairReportRequest, _output_path
from llm4mtl.semantic_tests.failure_report.surefire_view import _pair_surefire_evidence
from llm4mtl.serialization.hashing import directory_sha256, file_sha256
from llm4mtl.serialization.json_io import write_json_once


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
    recorded = resolve_recorded_execution(request)
    manifest = recorded.manifest
    identity = recorded.identity
    generated_execution = recorded.generated_execution
    suite_dir = recorded.suite_dir
    transformation_path = recorded.transformation_path
    execution_stage_evidence = recorded.stage_evidence

    context = resolve_report_context(request, recorded)
    syntax_check = context.syntax_check
    observation = context.observation
    reference_result = context.reference_result
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

    task_description = context.task_description
    metamodels = context.metamodels

    pair_result = {
        # Stated as null rather than omitted: a reader comparing report types
        # must see that this failure has no case and no assertion, not wonder
        # whether the fields were dropped.
        "test_case_id": None,
        "assertion_id": None,
        "semantic_status": context.semantic_status,
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
    validate_artifact("failure-report", report)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        repository_output = _repository_path(resolved_output)
        raise FailureReportError(
            f"report already exists and is immutable: {repository_output}"
        ) from exc
    return report
