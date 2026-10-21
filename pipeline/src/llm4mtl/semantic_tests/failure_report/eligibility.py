"""Whether a recorded failure is one Source Diagnosis may be asked about."""

from __future__ import annotations

from typing import Any

from llm4mtl.domain.observations import FailureStage

# The reasons that make a report diagnosis-eligible, one per report type.
CASE_ELIGIBLE_REASON = "parser_passed_and_semantic_test_failed"
PAIR_ELIGIBLE_REASON = "parser_passed_and_execution_failed_before_any_test"
# The observed facts about a per-case failure. Any one of them is enough.
OBSERVED_FAILURE_FACTS = (
    "target_model_snapshots",
    "assertion_expected_actual",
    "structured_difference",
    "recorded_exception",
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

    :func:`_not_about_the_pairing` states what both report types require. A
    per-case report also needs a recorded input model and at least one observed
    fact about the failure.

    An evaluated assertion is not required. A validated test that throws on a
    generated transformation has failed against it, and that is the most common
    shape of a transformation defect.

    Missing evidence makes the report ineligible; it does not stop the report.
    The report still records a real failure and says why it cannot be diagnosed.
    """
    common = _not_about_the_pairing(syntax_check, observation, reference_result)
    if common is not None:
        return common
    if not input_models:
        return "no_recorded_input_model"
    if not _has_observed_failure_evidence(observed_failure_evidence):
        return "no_observed_failure_evidence"
    return CASE_ELIGIBLE_REASON


def _has_observed_failure_evidence(observed_failure_evidence: dict[str, Any]) -> bool:
    return any(observed_failure_evidence[fact] for fact in OBSERVED_FAILURE_FACTS)


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

    Uses :func:`_not_about_the_pairing`, plus two conditions of its own: the
    execution was really attempted, and no narrower attribution exists. A run
    that *did* name a failing test method gets per-case reports; a pair-level
    report too would count the same failure twice.
    """
    common = _not_about_the_pairing(syntax_check, observation, reference_result)
    if common is not None:
        return common
    if not execution_attempted:
        return "execution_not_attempted"
    if per_test_failures:
        return "per_test_failure_available"
    if not any(preserved_failure_evidence.values()):
        return "no_preserved_failure_evidence"
    return PAIR_ELIGIBLE_REASON


def _not_about_the_pairing(
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
) -> str | None:
    """The reason no report type may be diagnosed, or ``None``.

    Both report types check these four conditions in this order. They live in
    one place so a change always reaches both types.

    A timeout or an infrastructure failure is excluded, not downgraded, because
    neither is evidence about the pairing.
    """
    if syntax_check["status"] != "passed":
        return "transformation_parser_check_failed"
    if observation["assertions_passed"] is True:
        return "semantic_test_passed"
    if observation.get("timed_out") is True or observation.get("failure_stage") in {
        FailureStage.TIMEOUT,
        FailureStage.INFRASTRUCTURE,
    }:
        return "failure_not_attributable_to_the_pairing"
    if reference_result.get("status") != "passed":
        return "reference_result_not_passing"
    return None
