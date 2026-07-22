"""The n8n <-> Python stage contract.

Python reports FACTS: a ``status`` (``passed`` | ``failed`` | ``infrastructure_error``)
and a domain ``outcome_code``. Routing lives only in n8n (see
``docs/n8n-python-contract.md``). This module translates the pipeline's internal
:class:`StageResult` into the standard stage-result payload and maps each contract
stage id to the adapter method that implements it.
"""

from __future__ import annotations

from typing import Any

from llm4mtl.experiment_runner.models import StageResult

SCHEMA_VERSION = "1.0"

# Contract stage id -> (orchestrator adapter attribute, method name).
STAGE_DISPATCH: dict[str, tuple[str, str]] = {
    "extract": ("tests", "extract"),
    "syntax-validation": ("parser", "parse"),
    "technical-validation": ("tests", "technical_validation"),
    "reference-validation": ("tests", "reference_validation"),
    "execution": ("transformations", "semantic_validation"),
}


def stage_status(result: StageResult) -> str:
    """Map the internal status to the contract's passed/failed/infrastructure_error."""
    if result.status in {"infrastructure_error", "error"}:
        return "infrastructure_error"
    if result.counts.get("infrastructure_errors", 0) > 0:
        return "infrastructure_error"
    return "failed" if result.domain_failures > 0 else "passed"


def outcome_code(stage: str, result: StageResult) -> str:
    """Domain outcome_code for a stage. ``infrastructure_error`` is orthogonal."""
    if stage_status(result) == "infrastructure_error":
        return "INFRASTRUCTURE_ERROR"
    counts = result.counts
    if stage == "extract":
        return "EXTRACTED" if counts.get("failed", 0) == 0 else "TEST_SPEC_INVALID"
    if stage == "syntax-validation":
        return "SYNTAX_VALID" if counts.get("failed", 0) == 0 else "SYNTAX_INVALID"
    if stage == "technical-validation":
        return "TECH_VALID" if counts.get("failed", 0) == 0 else "TECH_COMPILE_FAILED"
    if stage == "reference-validation":
        if counts.get("validated", 0) == 0 and counts.get("invalid", 0) == 0 and counts.get("skipped", 0) > 0:
            return "SKIPPED_MISSING_TECHNICAL_VALIDATION"
        return "REFERENCE_VALIDATED" if counts.get("invalid", 0) == 0 else "REFERENCE_VALIDATION_FAILED"
    if stage == "execution":
        return "SEMANTIC_PASSED" if counts.get("failed", 0) == 0 else "SEMANTIC_EXECUTION_FAILED"
    return "UNKNOWN"


def _artifacts(result: StageResult) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for key in ("results_file", "diagnostics"):
        value = result.details.get(key)
        if isinstance(value, str):
            artifacts[key] = value
    return artifacts


def to_stage_payload(stage: str, result: StageResult, attempt: int | None = None) -> dict[str, Any]:
    """Build the standard stage-result payload n8n reads."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "status": stage_status(result),
        "outcome_code": outcome_code(stage, result),
        "counts": dict(result.counts),
        "artifacts": _artifacts(result),
    }
    if attempt is not None:
        payload["attempt"] = attempt
    return payload
