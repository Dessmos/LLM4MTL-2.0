"""The parts of a failure report that both report types share.

A per-case report and a pair-level report differ in their body and in most of
their evidence bundle. The envelope, the ``versions`` and ``execution`` blocks,
the ``source_diagnosis`` block, the start of the bundle, and the write-once step
are the same, and are built here once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.semantic_tests.failure_report.artifacts import (
    _cited,
    _repository_path,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.evidence import (
    RecordedExecution,
    ReportContext,
)
from llm4mtl.semantic_tests.failure_report.models import SCHEMA_VERSION
from llm4mtl.serialization.hashing import directory_sha256, file_sha256
from llm4mtl.serialization.json_io import write_json_once

FAILURE_REPORT_SCHEMA = "failure-report"
# The verdicts a diagnosis may return. The report schema allows only these.
ALLOWED_CLASSIFICATIONS = ("transformation_defect", "test_defect", "ambiguous")
# The fields every diagnosis result must carry. A per-case result adds more.
REQUIRED_RESULT_FIELDS = (
    "classification",
    "confidence",
    "reasoning_summary",
    "evidence",
)


def report_document(
    *,
    report_type: str,
    recorded: RecordedExecution,
    context: ReportContext,
    body_key: str,
    body: dict[str, Any],
    source_diagnosis: dict[str, Any],
) -> dict[str, Any]:
    """The whole report: the shared envelope around one type-specific body."""
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": report_type,
        "identity": recorded.identity,
        "task_context": {
            "original_description": context.task_description,
            "metamodel_constraints": context.metamodels,
        },
        body_key: body,
        "source_diagnosis": source_diagnosis,
    }


def source_diagnosis_section(
    *,
    is_eligible: bool,
    reason: str,
    evidence_bundle: dict[str, Any] | None,
    required_result_fields: tuple[str, ...],
) -> dict[str, Any]:
    """What a diagnosis may be asked, and what its answer must contain."""
    return {
        "eligible": is_eligible,
        "reason": reason,
        "evidence_bundle": evidence_bundle,
        "allowed_classifications": list(ALLOWED_CLASSIFICATIONS),
        "required_result_fields": list(required_result_fields),
    }


def versions_section(recorded: RecordedExecution) -> dict[str, Any]:
    """The hashes and paths of the generated transformation and test."""
    return {
        "generated_transformation": {
            "sha256": file_sha256(recorded.transformation_path),
            "path": _repository_path(recorded.transformation_path),
        },
        "generated_test": {
            "sha256": directory_sha256(recorded.suite_dir),
            "path": _repository_path(recorded.suite_dir),
            "renderer_version": recorded.manifest.get("provenance", {}).get(
                "renderer_version"
            ),
        },
    }


def execution_section(
    context: ReportContext, recorded: RecordedExecution, error: dict[str, Any]
) -> dict[str, Any]:
    """The recorded observation, its stage evidence, and what went wrong."""
    return {
        "observation": context.observation,
        "stage_evidence": recorded.stage_evidence,
        "error": error,
    }


def recorded_error_summary(observation: dict[str, Any]) -> str:
    """The observation's ``error_summary``, or ``""`` when it recorded none."""
    return str(observation.get("error_summary", ""))


def bundle_head(context: ReportContext, transformation_path: Path) -> dict[str, Any]:
    """The first bundle fields: the task, the metamodels, and the transformation."""
    return {
        "original_task_description": context.task_description["content"],
        "relevant_source_and_target_metamodel_constraints": [
            _cited(metamodel) for metamodel in context.metamodels
        ],
        "generated_transformation": _cited(_text_artifact(transformation_path)),
    }


def reference_verdict(reference_result: dict[str, Any]) -> dict[str, Any]:
    """The reference result as a bundle states it: a verdict, not a document."""
    reference_observation = reference_result["observation"]
    return {
        "status": reference_result["status"],
        "assertions_passed": (
            reference_observation["assertions_passed"]
            if reference_observation is not None
            else None
        ),
    }


def execution_summary(observation: dict[str, Any]) -> dict[str, Any]:
    """The observation fields that open a bundle's ``generated_execution_summary``."""
    return {
        "failure_stage": observation.get("failure_stage"),
        "assertions_evaluated": observation.get("assertions_evaluated"),
        "assertions_passed": observation.get("assertions_passed"),
        "error_summary": observation.get("error_summary"),
    }


def persist_once(report: dict[str, Any], resolved_output: Path) -> None:
    """Validate ``report`` and create it at ``resolved_output``; never overwrite."""
    validate_artifact(FAILURE_REPORT_SCHEMA, report)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        repository_output = _repository_path(resolved_output)
        raise FailureReportError(
            f"report already exists and is immutable: {repository_output}"
        ) from exc
