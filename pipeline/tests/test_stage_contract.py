from __future__ import annotations

import unittest

from llm4mtl.experiment_runner.models import StageResult
from llm4mtl.stage_contract import outcome_code, stage_status, to_stage_payload


def result(name: str, status: str, **counts: int) -> StageResult:
    return StageResult(name, status, dict(counts))


class OutcomeCodeTests(unittest.TestCase):
    def test_syntax_validation(self) -> None:
        self.assertEqual(
            "SYNTAX_VALID",
            outcome_code("syntax-validation", result("transformation_parsing", "completed", selected=4, passed=4, failed=0)),
        )
        self.assertEqual(
            "SYNTAX_INVALID",
            outcome_code("syntax-validation", result("transformation_parsing", "completed", selected=4, passed=3, failed=1)),
        )

    def test_reference_validation(self) -> None:
        self.assertEqual(
            "REFERENCE_VALIDATED",
            outcome_code("reference-validation", result("reference_validation", "completed", validated=1, invalid=0)),
        )
        self.assertEqual(
            "REFERENCE_VALIDATION_FAILED",
            outcome_code("reference-validation", result("reference_validation", "completed", validated=0, invalid=1)),
        )
        self.assertEqual(
            "SKIPPED_MISSING_TECHNICAL_VALIDATION",
            outcome_code("reference-validation", result("reference_validation", "completed", validated=0, invalid=0, skipped=1)),
        )

    def test_execution(self) -> None:
        self.assertEqual(
            "SEMANTIC_PASSED",
            outcome_code("execution", result("transformation_validation", "completed", passed=2, failed=0)),
        )
        self.assertEqual(
            "SEMANTIC_EXECUTION_FAILED",
            outcome_code("execution", result("transformation_validation", "completed", passed=1, failed=1)),
        )

    def test_infrastructure_error_is_orthogonal(self) -> None:
        infra = result("reference_validation", "completed", validated=1, invalid=0, infrastructure_errors=1)
        self.assertEqual("infrastructure_error", stage_status(infra))
        self.assertEqual("INFRASTRUCTURE_ERROR", outcome_code("reference-validation", infra))


class PayloadTests(unittest.TestCase):
    def test_payload_shape(self) -> None:
        payload = to_stage_payload(
            "syntax-validation",
            result("transformation_parsing", "completed", selected=1, passed=1, failed=0),
            attempt=1,
        )
        self.assertEqual(
            {"schema_version", "stage", "status", "outcome_code", "counts", "artifacts", "attempt"},
            set(payload),
        )
        self.assertEqual("syntax-validation", payload["stage"])
        self.assertEqual("passed", payload["status"])
        self.assertEqual(1, payload["attempt"])


if __name__ == "__main__":
    unittest.main()
