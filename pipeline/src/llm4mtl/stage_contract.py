"""The n8n <-> Python stage contract.

Python reports FACTS: a ``status`` (``passed`` | ``failed`` | ``skipped`` |
``infrastructure_error``) and a domain ``outcome_code``. Routing lives only in n8n
(see ``docs/n8n-python-contract.md``). This module translates the pipeline's
internal :class:`StageResult` into the standard stage-result payload and maps each
contract stage id to the adapter method that implements it.

``skipped`` is a first-class outcome: a stage that produced no observation at all
is not a stage that passed, and folding the two together would let missing data
count as success in every downstream metric.
"""

from __future__ import annotations

from typing import Any, Callable

from llm4mtl.experiment_runner.models import StageResult

SCHEMA_VERSION = "2.0"

# Contract stage id -> (orchestrator adapter attribute, method name).
STAGE_DISPATCH: dict[str, tuple[str, str]] = {
    "extract": ("tests", "extract"),
    "syntax-validation": ("parser", "parse"),
    "technical-validation": ("tests", "technical_validation"),
    "reference-validation": ("tests", "reference_validation"),
    "execution": ("transformations", "semantic_validation"),
}

# Internal pipeline stage name -> contract stage id. The local runner names its
# stages after the code that runs them; persisted evidence always uses the
# contract id, so a run directory reads the same whoever wrote it.
CONTRACT_STAGE_IDS: dict[str, str] = {
    "extraction": "extract",
    "transformation_parsing": "syntax-validation",
    "technical_validation": "technical-validation",
    "reference_validation": "reference-validation",
    "transformation_validation": "execution",
}

# Outcome code for a stage that ran but observed nothing, when the stage itself
# recorded no more specific ``skip_reason``.
DEFAULT_SKIP_OUTCOME_CODES: dict[str, str] = {
    "reference-validation": "SKIPPED_MISSING_TECHNICAL_VALIDATION",
    "execution": "SKIPPED_NO_PARSED_TRANSFORMATIONS",
}


def contract_stage_id(internal_name: str) -> str:
    """Translate an internal pipeline stage name into its contract stage id."""
    try:
        return CONTRACT_STAGE_IDS[internal_name]
    except KeyError as exc:
        known = ", ".join(sorted(CONTRACT_STAGE_IDS))
        raise KeyError(
            f"unknown pipeline stage '{internal_name}' (known: {known})"
        ) from exc


def is_skipped(stage: str, result: StageResult) -> bool:
    """True when the stage executed nothing and therefore observed nothing.

    Every stage that can judge nothing needs a branch here. Without one, a stage
    whose pairs all landed in ``skipped`` or ``inconclusive`` has no recorded
    failure, and the final ``passed`` fallthrough in :func:`stage_status` reports
    a run that established nothing as a passing one.
    """
    if result.status == "skipped":
        return True
    counts = result.counts
    if stage == "reference-validation":
        return (
            counts.get("validated", 0) == 0
            and counts.get("invalid", 0) == 0
            and counts.get("skipped", 0) > 0
        )
    if stage == "execution":
        return counts.get("evaluated", 0) == 0 and counts.get("skipped", 0) > 0
    return False


def stage_status(stage: str, result: StageResult) -> str:
    """Map the internal status to the contract's passed/failed/skipped/infrastructure_error."""
    if result.status in {"infrastructure_error", "error"}:
        return "infrastructure_error"
    if result.counts.get("infrastructure_errors", 0) > 0:
        return "infrastructure_error"
    if is_skipped(stage, result):
        return "skipped"
    return "failed" if result.domain_failures > 0 else "passed"


def _extract_outcome(counts: dict[str, int]) -> str:
    return "EXTRACTED" if counts.get("failed", 0) == 0 else "TEST_SPEC_INVALID"


def _syntax_outcome(counts: dict[str, int]) -> str:
    return "SYNTAX_VALID" if counts.get("failed", 0) == 0 else "SYNTAX_INVALID"


def _technical_outcome(counts: dict[str, int]) -> str:
    # Vocabulary fixed by docs/n8n-python-contract.md: the distinction is
    # compile failure versus execution failure, while an unusable artifact
    # reuses the test-spec code that already means "regenerate the test".
    if counts.get("compile_failed", 0) > 0:
        return "TECH_COMPILE_FAILED"
    if counts.get("failed", 0) > 0:
        return "TECH_EXEC_FAILED"
    return "TEST_SPEC_INVALID" if counts.get("invalid", 0) > 0 else "TECH_VALID"


def _reference_outcome(counts: dict[str, int]) -> str:
    return (
        "REFERENCE_VALIDATED"
        if counts.get("invalid", 0) == 0
        else "REFERENCE_VALIDATION_FAILED"
    )


def _execution_outcome(counts: dict[str, int]) -> str:
    return (
        "SEMANTIC_PASSED"
        if counts.get("failed", 0) == 0
        else "SEMANTIC_EXECUTION_FAILED"
    )


OUTCOME_CODE_RESOLVERS: dict[str, Callable[[dict[str, int]], str]] = {
    "extract": _extract_outcome,
    "syntax-validation": _syntax_outcome,
    "technical-validation": _technical_outcome,
    "reference-validation": _reference_outcome,
    "execution": _execution_outcome,
}


def outcome_code(stage: str, result: StageResult) -> str:
    """Domain outcome_code for a stage. ``infrastructure_error`` is orthogonal."""
    status = stage_status(stage, result)
    if status == "infrastructure_error":
        return "INFRASTRUCTURE_ERROR"
    if status == "skipped":
        recorded_reason = result.details.get("skip_reason")
        if isinstance(recorded_reason, str) and recorded_reason:
            return recorded_reason
        return DEFAULT_SKIP_OUTCOME_CODES.get(stage, "SKIPPED")
    resolver = OUTCOME_CODE_RESOLVERS.get(stage)
    return resolver(result.counts) if resolver is not None else "UNKNOWN"


def _artifacts(result: StageResult) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for key in ("results_file", "diagnostics"):
        value = result.details.get(key)
        if isinstance(value, str):
            artifacts[key] = value
    return artifacts


def to_stage_payload(
    stage: str, result: StageResult, attempt: int | None = None
) -> dict[str, Any]:
    """Build the standard stage-result payload n8n reads."""
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": stage,
        "status": stage_status(stage, result),
        "outcome_code": outcome_code(stage, result),
        "counts": dict(result.counts),
        "artifacts": _artifacts(result),
    }
    if attempt is not None:
        payload["attempt"] = attempt
    return payload
