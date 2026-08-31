"""Whether a recorded failure is one Source Diagnosis may be asked about."""

from __future__ import annotations

from typing import Any


def _diagnosis_reason(
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
    *,
    input_models: list[dict[str, Any]],
    observed_failure_evidence: dict[str, Any],
) -> str:
    """Why this failure is or is not a case Source Diagnosis may be asked about.

    :func:`_not_about_the_pairing` establishes what both report types require;
    what is added here is that an input model was recorded and that enough
    execution evidence survived to say what happened.

    Note what is *not* a condition: that an assertion was evaluated. A validated
    test that throws on a generated transformation has failed against it, and
    that failure is exactly what Source Diagnosis exists to attribute — to the
    transformation, to the test, or to neither. Requiring a JUnit assertion
    failure would silently exclude the most common shape of a transformation
    defect.

    Missing evidence downgrades eligibility rather than aborting: the report is
    still the run's record of a real failure, and saying why it cannot be
    diagnosed is more useful than refusing to write it.
    """
    common = _not_about_the_pairing(syntax_check, observation, reference_result)
    if common is not None:
        return common
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

    Shares :func:`_not_about_the_pairing` with the per-case rule, plus two
    conditions specific to this report type: the execution has to have actually
    been attempted, and no narrower attribution may exist. A run that *did* name a failing test method
    is not a pair-level case — it has a per-case report, and producing both
    would put the same failure into the population twice.
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
    return "parser_passed_and_execution_failed_before_any_test"


def _not_about_the_pairing(
    syntax_check: dict[str, Any],
    observation: dict[str, Any],
    reference_result: dict[str, Any],
) -> str | None:
    """The conditions under which no report type may be diagnosed, or ``None``.

    Both report types establish these four in this order, and they answered
    them identically when each spelled them out for itself. Stated once, so a
    change to what counts as attributable cannot reach one report type and not
    the other.

    A timeout or an infrastructure failure is excluded here rather than
    downgraded, because neither is evidence about the pairing at all.
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
    return None
