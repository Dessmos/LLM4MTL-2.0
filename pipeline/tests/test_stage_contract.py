from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm4mtl.experiment_runner.models import StageResult
from llm4mtl.experiment_runner.orchestrator import run_status
from llm4mtl.stage_contract import outcome_code, stage_status, to_stage_payload


def result(name: str, status: str, **counts: int) -> StageResult:
    return StageResult(name, status, dict(counts))


def skipped(name: str, reason: str = "", **counts: int) -> StageResult:
    details = {"skip_reason": reason} if reason else {}
    return StageResult(name, "skipped", dict(counts), details)


class OutcomeCodeTests(unittest.TestCase):

    def test_syntax_validation(self) -> None:
        self.assertEqual(
            "SYNTAX_VALID",
            outcome_code(
                "syntax-validation",
                result(
                    "transformation_parsing",
                    "completed",
                    selected=4,
                    passed=4,
                    failed=0,
                ),
            ),
        )
        self.assertEqual(
            "SYNTAX_INVALID",
            outcome_code(
                "syntax-validation",
                result(
                    "transformation_parsing",
                    "completed",
                    selected=4,
                    passed=3,
                    failed=1,
                ),
            ),
        )

    def test_reference_validation(self) -> None:
        self.assertEqual(
            "REFERENCE_VALIDATED",
            outcome_code(
                "reference-validation",
                result("reference_validation", "completed", validated=1, invalid=0),
            ),
        )
        self.assertEqual(
            "REFERENCE_VALIDATION_FAILED",
            outcome_code(
                "reference-validation",
                result("reference_validation", "completed", validated=0, invalid=1),
            ),
        )
        self.assertEqual(
            "SKIPPED_MISSING_TECHNICAL_VALIDATION",
            outcome_code(
                "reference-validation",
                result(
                    "reference_validation",
                    "completed",
                    validated=0,
                    invalid=0,
                    skipped=1,
                ),
            ),
        )

    def test_execution(self) -> None:
        self.assertEqual(
            "SEMANTIC_PASSED",
            outcome_code(
                "execution",
                result("transformation_validation", "completed", passed=2, failed=0),
            ),
        )
        self.assertEqual(
            "SEMANTIC_EXECUTION_FAILED",
            outcome_code(
                "execution",
                result("transformation_validation", "completed", passed=1, failed=1),
            ),
        )

    def test_infrastructure_error_is_orthogonal(self) -> None:
        infra = result(
            "reference_validation",
            "completed",
            validated=1,
            invalid=0,
            infrastructure_errors=1,
        )
        self.assertEqual(
            "infrastructure_error", stage_status("reference-validation", infra)
        )
        self.assertEqual(
            "INFRASTRUCTURE_ERROR", outcome_code("reference-validation", infra)
        )


class SkipSemanticsTests(unittest.TestCase):
    """A stage that observed nothing is never a stage that passed."""

    def test_reference_validation_that_executed_nothing_is_skipped(self) -> None:
        nothing_executed = result(
            "reference_validation",
            "completed",
            selected=3,
            validated=0,
            invalid=0,
            skipped=3,
        )
        self.assertEqual(
            "skipped", stage_status("reference-validation", nothing_executed)
        )
        self.assertEqual(
            "SKIPPED_MISSING_TECHNICAL_VALIDATION",
            outcome_code("reference-validation", nothing_executed),
        )

    def test_skipped_execution_reports_its_recorded_reason(self) -> None:
        no_transformations = skipped(
            "transformation_validation", "SKIPPED_NO_PARSED_TRANSFORMATIONS", skipped=1
        )
        self.assertEqual("skipped", stage_status("execution", no_transformations))
        self.assertEqual(
            "SKIPPED_NO_PARSED_TRANSFORMATIONS",
            outcome_code("execution", no_transformations),
        )

    def test_a_stage_with_observations_is_not_skipped(self) -> None:
        partially_skipped = result(
            "reference_validation",
            "completed",
            selected=3,
            validated=2,
            invalid=0,
            skipped=1,
        )
        self.assertEqual(
            "passed", stage_status("reference-validation", partially_skipped)
        )
        self.assertEqual(
            "REFERENCE_VALIDATED",
            outcome_code("reference-validation", partially_skipped),
        )

    def test_skipped_status_is_declared_by_the_json_schema(self) -> None:
        payload = to_stage_payload(
            "execution", skipped("transformation_validation", skipped=1)
        )
        schema_path = (
            Path(__file__).resolve().parents[2] / "schemas" / "stage-result.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertIn(payload["status"], schema["properties"]["status"]["enum"])

    def test_a_run_with_a_skipped_stage_is_not_completed(self) -> None:
        results = [
            result("extraction", "completed", selected=1, failed=0),
            skipped(
                "transformation_validation",
                "SKIPPED_NO_PARSED_TRANSFORMATIONS",
                skipped=1,
            ),
        ]
        self.assertEqual("incomplete", run_status(results))


class PayloadTests(unittest.TestCase):

    def test_payload_shape(self) -> None:
        payload = to_stage_payload(
            "syntax-validation",
            result(
                "transformation_parsing", "completed", selected=1, passed=1, failed=0
            ),
            attempt=1,
        )
        self.assertEqual(
            {
                "schema_version",
                "stage",
                "status",
                "outcome_code",
                "counts",
                "artifacts",
                "attempt",
            },
            set(payload),
        )
        self.assertEqual("syntax-validation", payload["stage"])
        self.assertEqual("passed", payload["status"])
        self.assertEqual(1, payload["attempt"])

    def test_an_execution_that_judged_nothing_never_reports_passed(self) -> None:
        """No verdict is not a pass.

        ``evaluated`` is the denominator of semantic correctness. A stage that
        ran pairs but reached a verdict on none of them has an empty numerator
        AND an empty denominator, and the contract's final ``passed``
        fallthrough used to turn that into SEMANTIC_PASSED.
        """
        nothing_judged = result(
            "transformation_validation",
            "completed",
            execution_pairs=3,
            evaluated=0,
            passed=0,
            failed=0,
            skipped=3,
        )

        self.assertEqual("skipped", stage_status("execution", nothing_judged))
        self.assertNotEqual(
            "SEMANTIC_PASSED", outcome_code("execution", nothing_judged)
        )

    def test_unrunnable_pairs_do_not_block_a_verdict_on_the_others(self) -> None:
        """A partly unrunnable run still reports the verdict it did reach."""
        partly_judged = result(
            "transformation_validation",
            "completed",
            execution_pairs=3,
            evaluated=2,
            passed=2,
            failed=0,
            skipped=1,
        )

        self.assertEqual("passed", stage_status("execution", partly_judged))
        self.assertEqual("SEMANTIC_PASSED", outcome_code("execution", partly_judged))

    def test_payload_shape_is_declared_by_json_schema(self) -> None:
        payload = to_stage_payload(
            "extract",
            result("extraction", "completed", selected=1, failed=0),
            attempt=1,
        )
        schema_path = (
            Path(__file__).resolve().parents[2] / "schemas" / "stage-result.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertLessEqual(set(payload), set(properties))
        self.assertIn(payload["stage"], properties["stage"]["enum"])
        self.assertIn(payload["status"], properties["status"]["enum"])
        self.assertTrue(set(schema["required"]).issubset(payload))


if __name__ == "__main__":
    unittest.main()
