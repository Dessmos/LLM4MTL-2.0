from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm4mtl import run_store
from llm4mtl.evaluation.experiment_aggregation import aggregate_stage
from llm4mtl.evaluation.experiment_significance import mcnemar


class AggregationTests(unittest.TestCase):
    def test_aggregate_stage_over_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def make_run(run_id: str, model: str, outcome: str) -> None:
                paths = run_store.create_run(
                    root, run_id, {"transformation_model": model, "pipeline_variant": "full", "strategy": "grammar"}
                )
                run_store.record_attempt(
                    paths,
                    "syntax-validation",
                    {"outcome_code": outcome, "status": "passed" if outcome == "SYNTAX_VALID" else "failed"},
                )

            make_run("r1", "claude-sonnet-4", "SYNTAX_VALID")
            make_run("r2", "claude-sonnet-4", "SYNTAX_INVALID")
            make_run("r3", "gpt-5", "SYNTAX_VALID")

            agg = aggregate_stage(root, ["r1", "r2", "r3"], "syntax-validation")
            self.assertEqual(3, agg["runs"])
            self.assertEqual(2, agg["totals"]["SYNTAX_VALID"])
            self.assertEqual(1, agg["totals"]["SYNTAX_INVALID"])
            self.assertEqual(
                {"SYNTAX_VALID": 1, "SYNTAX_INVALID": 1},
                agg["by_group"]["full/claude-sonnet-4/grammar"],
            )


class SignificanceTests(unittest.TestCase):
    def test_identical_outcomes_are_not_significant(self) -> None:
        result = mcnemar([True, True, False, False], [True, True, False, False])
        self.assertEqual(0, result["baseline_only"])
        self.assertEqual(0, result["variant_only"])
        self.assertEqual(1.0, result["p_value"])

    def test_maximally_discordant_is_significant(self) -> None:
        result = mcnemar([True] * 8, [False] * 8)
        self.assertEqual(8, result["baseline_only"])
        self.assertEqual(0, result["variant_only"])
        self.assertLess(result["p_value"], 0.05)


if __name__ == "__main__":
    unittest.main()
