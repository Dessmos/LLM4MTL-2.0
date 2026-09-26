"""The n8n <-> Python stage contract.

Python reports FACTS: a ``status`` (``passed`` | ``failed`` | ``skipped`` |
``infrastructure_error``) and a domain ``outcome_code``. Routing lives only in n8n
(see ``docs/n8n-python-contract.md``). This module translates the pipeline's
internal :class:`StageResult` into the standard stage-result payload. Which code
implements each stage id is :mod:`llm4mtl.stages.dispatch`'s concern.

``skipped`` is a first-class outcome: a stage that produced no observation at all
is not a stage that passed, and folding the two together would let missing data
count as success in every downstream metric.
"""

from __future__ import annotations

from typing import Any, Callable

from llm4mtl.stages.models import (
    EXTRACTION_STAGE_NAME,
    REFERENCE_VALIDATION_STAGE_NAME,
    TECHNICAL_VALIDATION_STAGE_NAME,
    TRANSFORMATION_PARSING_STAGE_NAME,
    TRANSFORMATION_VALIDATION_STAGE_NAME,
    StageResult,
)
from llm4mtl.vocabulary import (
    EXECUTION_STAGE_ID,
    EXTRACT_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_ID,
    SYNTAX_VALIDATION_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_ID,
)

SCHEMA_VERSION = "2.0"

# Internal pipeline stage name -> contract stage id. The local runner names its
# stages after the code that runs them; persisted evidence always uses the
# contract id, so a run directory reads the same whoever wrote it.
CONTRACT_STAGE_IDS: dict[str, str] = {
    EXTRACTION_STAGE_NAME: EXTRACT_STAGE_ID,
    TRANSFORMATION_PARSING_STAGE_NAME: SYNTAX_VALIDATION_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_NAME: TECHNICAL_VALIDATION_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_NAME: REFERENCE_VALIDATION_STAGE_ID,
    TRANSFORMATION_VALIDATION_STAGE_NAME: EXECUTION_STAGE_ID,
}
CONTRACT_STAGES = frozenset(CONTRACT_STAGE_IDS.values())

# Outcome codes, as docs/n8n-python-contract.md spells them.
EXTRACTED = "EXTRACTED"
TEST_SPEC_INVALID = "TEST_SPEC_INVALID"
SYNTAX_VALID = "SYNTAX_VALID"
SYNTAX_INVALID = "SYNTAX_INVALID"
TECH_VALID = "TECH_VALID"
TECH_COMPILE_FAILED = "TECH_COMPILE_FAILED"
TECH_EXEC_FAILED = "TECH_EXEC_FAILED"
REFERENCE_VALIDATED = "REFERENCE_VALIDATED"
REFERENCE_VALIDATION_FAILED = "REFERENCE_VALIDATION_FAILED"
SEMANTIC_PASSED = "SEMANTIC_PASSED"
SEMANTIC_EXECUTION_FAILED = "SEMANTIC_EXECUTION_FAILED"
INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
SKIPPED = "SKIPPED"
UNKNOWN = "UNKNOWN"

# The execution stage had no parsed transformation to judge. The stage records
# it as its own skip reason, and it is also the default for that stage.
SKIPPED_NO_PARSED_TRANSFORMATIONS = "SKIPPED_NO_PARSED_TRANSFORMATIONS"

# Outcome code for a stage that ran but observed nothing, when the stage itself
# recorded no more specific ``skip_reason``.
DEFAULT_SKIP_OUTCOME_CODES: dict[str, str] = {
    REFERENCE_VALIDATION_STAGE_ID: "SKIPPED_MISSING_TECHNICAL_VALIDATION",
    EXECUTION_STAGE_ID: SKIPPED_NO_PARSED_TRANSFORMATIONS,
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
    if stage == REFERENCE_VALIDATION_STAGE_ID:
        return (
            counts.get("validated", 0) == 0
            and counts.get("invalid", 0) == 0
            and counts.get("skipped", 0) > 0
        )
    if stage == EXECUTION_STAGE_ID:
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
    return EXTRACTED if counts.get("failed", 0) == 0 else TEST_SPEC_INVALID


def _syntax_outcome(counts: dict[str, int]) -> str:
    return SYNTAX_VALID if counts.get("failed", 0) == 0 else SYNTAX_INVALID


def _technical_outcome(counts: dict[str, int]) -> str:
    # Vocabulary fixed by docs/n8n-python-contract.md: the distinction is
    # compile failure versus execution failure, while an unusable artifact
    # reuses the test-spec code that already means "regenerate the test".
    if counts.get("compile_failed", 0) > 0:
        return TECH_COMPILE_FAILED
    if counts.get("failed", 0) > 0:
        return TECH_EXEC_FAILED
    return TEST_SPEC_INVALID if counts.get("invalid", 0) > 0 else TECH_VALID


def _reference_outcome(counts: dict[str, int]) -> str:
    return (
        REFERENCE_VALIDATED
        if counts.get("invalid", 0) == 0
        else REFERENCE_VALIDATION_FAILED
    )


def _execution_outcome(counts: dict[str, int]) -> str:
    return (
        SEMANTIC_PASSED if counts.get("failed", 0) == 0 else SEMANTIC_EXECUTION_FAILED
    )


OUTCOME_CODE_RESOLVERS: dict[str, Callable[[dict[str, int]], str]] = {
    EXTRACT_STAGE_ID: _extract_outcome,
    SYNTAX_VALIDATION_STAGE_ID: _syntax_outcome,
    TECHNICAL_VALIDATION_STAGE_ID: _technical_outcome,
    REFERENCE_VALIDATION_STAGE_ID: _reference_outcome,
    EXECUTION_STAGE_ID: _execution_outcome,
}


def outcome_code(stage: str, result: StageResult) -> str:
    """Domain outcome_code for a stage. ``infrastructure_error`` is orthogonal."""
    status = stage_status(stage, result)
    if status == "infrastructure_error":
        return INFRASTRUCTURE_ERROR
    if status == "skipped":
        recorded_reason = result.details.get("skip_reason")
        if isinstance(recorded_reason, str) and recorded_reason:
            return recorded_reason
        return DEFAULT_SKIP_OUTCOME_CODES.get(stage, SKIPPED)
    resolver = OUTCOME_CODE_RESOLVERS.get(stage)
    return resolver(result.counts) if resolver is not None else UNKNOWN


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
