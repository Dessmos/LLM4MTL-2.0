"""Which recorded failures Source Diagnosis may be asked about, and why not.

Each refusal reason decides whether a failure enters the diagnosed population,
so every reason is pinned here with small hand-written facts.
"""

from __future__ import annotations

import unittest
from typing import Any

from llm4mtl.semantic_tests.failure_report.eligibility import (
    CASE_ELIGIBLE_REASON,
    PAIR_ELIGIBLE_REASON,
    _diagnosis_reason,
    _pair_diagnosis_reason,
)
from llm4mtl.semantic_tests.failure_report.semantic_cases import rendered_method_name

PARSED = {"status": "passed"}
FAILED_ON_GENERATED = {
    "assertions_passed": False,
    "timed_out": False,
    "failure_stage": "engine_runtime",
}
PASSED_ON_REFERENCE = {"status": "passed"}
PRESERVED = {
    "recorded_exception": True,
    "system_err": False,
    "error_summary": False,
    "maven_log": False,
}
NOTHING_PRESERVED = {fact: False for fact in PRESERVED}
NOTHING_OBSERVED = {
    "target_model_snapshots": 0,
    "assertion_expected_actual": False,
    "structured_difference": False,
    "recorded_exception": False,
}
INPUT_MODELS = [{"model": {"name": "IN"}, "artifact": {"path": "in.model"}}]


def _pair_reason(**overrides: Any) -> str:
    facts: dict[str, Any] = {
        "syntax_check": PARSED,
        "observation": FAILED_ON_GENERATED,
        "reference_result": PASSED_ON_REFERENCE,
        "execution_attempted": True,
        "per_test_failures": [],
        "preserved_failure_evidence": PRESERVED,
        **overrides,
    }
    return _pair_diagnosis_reason(
        facts.pop("syntax_check"),
        facts.pop("observation"),
        facts.pop("reference_result"),
        **facts,
    )


def _case_reason(**overrides: Any) -> str:
    facts: dict[str, Any] = {
        "syntax_check": PARSED,
        "observation": FAILED_ON_GENERATED,
        "reference_result": PASSED_ON_REFERENCE,
        "input_models": INPUT_MODELS,
        "observed_failure_evidence": {**NOTHING_OBSERVED, "recorded_exception": True},
        **overrides,
    }
    return _diagnosis_reason(
        facts.pop("syntax_check"),
        facts.pop("observation"),
        facts.pop("reference_result"),
        **facts,
    )


class PairDiagnosisReasonTests(unittest.TestCase):

    def test_a_complete_pair_failure_is_eligible(self) -> None:
        self.assertEqual(PAIR_ELIGIBLE_REASON, _pair_reason())

    def test_each_pair_refusal_names_its_reason(self) -> None:
        cases = {
            "execution_not_attempted": {"execution_attempted": False},
            "per_test_failure_available": {
                "per_test_failures": [
                    {"test_class": "T", "test_method": "m", "status": "failed"}
                ]
            },
            "no_preserved_failure_evidence": {
                "preserved_failure_evidence": NOTHING_PRESERVED
            },
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(reason, _pair_reason(**overrides))

    def test_the_shared_conditions_are_checked_before_the_pair_ones(self) -> None:
        self.assertEqual(
            "transformation_parser_check_failed",
            _pair_reason(syntax_check={"status": "failed"}, execution_attempted=False),
        )


class CaseDiagnosisReasonTests(unittest.TestCase):

    def test_any_one_observed_fact_is_enough(self) -> None:
        facts = {
            "target_model_snapshots": 1,
            "assertion_expected_actual": True,
            "structured_difference": True,
            "recorded_exception": True,
        }
        for fact, value in facts.items():
            with self.subTest(fact=fact):
                observed = {**NOTHING_OBSERVED, fact: value}
                self.assertEqual(
                    CASE_ELIGIBLE_REASON,
                    _case_reason(observed_failure_evidence=observed),
                )

    def test_each_case_refusal_names_its_reason(self) -> None:
        cases = {
            "no_recorded_input_model": {"input_models": []},
            "no_observed_failure_evidence": {
                "observed_failure_evidence": NOTHING_OBSERVED
            },
            "semantic_test_passed": {
                "observation": {**FAILED_ON_GENERATED, "assertions_passed": True}
            },
            "failure_not_attributable_to_the_pairing": {
                "observation": {**FAILED_ON_GENERATED, "timed_out": True}
            },
            "reference_result_not_passing": {"reference_result": {"status": "not_run"}},
        }
        for reason, overrides in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(reason, _case_reason(**overrides))


class SemanticCaseNamingTests(unittest.TestCase):

    def test_a_case_without_a_name_renders_no_method(self) -> None:
        self.assertEqual("", rendered_method_name({"id": "c1"}))


if __name__ == "__main__":
    unittest.main()
