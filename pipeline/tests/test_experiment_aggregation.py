from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm4mtl import run_store
from llm4mtl.provenance import build_provenance
from llm4mtl.stage_contract import SCHEMA_VERSION as STAGE_SCHEMA_VERSION
from llm4mtl.evaluation.experiment_aggregation import aggregate_stage
from llm4mtl.evaluation.experiment_significance import mcnemar


class AggregationTests(unittest.TestCase):
    def test_aggregate_stage_over_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def make_run(run_id: str, model: str, outcome: str) -> None:
                paths = run_store.create_run(
                    root,
                    run_id,
                    {
                        "language": "etl",
                        "task": "Tree2Graph",
                        "transformation_model": model,
                        "test_generation_model": "gpt-5",
                        "transformation_strategy": "grammar",
                        "test_generation_strategy": "few_shot",
                        "seed": 1,
                        "pipeline_variant": "full",
                        "provenance": build_provenance("etl", "Tree2Graph"),
                    },
                )
                run_store.record_attempt(
                    paths,
                    "syntax-validation",
                    {
                        "schema_version": STAGE_SCHEMA_VERSION,
                        "outcome_code": outcome,
                        "status": "passed" if outcome == "SYNTAX_VALID" else "failed",
                    },
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
                agg["by_group"]["full/claude-sonnet-4/grammar/gpt-5/few_shot"],
            )
            self.assertEqual(agg["by_group"], agg["by_configured_group"])

    def test_refined_outcome_uses_the_matching_actual_generation_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = run_store.create_run(
                root,
                "attribution-1",
                {
                    "language": "etl",
                    "task": "Tree2Graph",
                    "transformation_model": "gpt-5",
                    "test_generation_model": "gpt-5",
                    "transformation_strategy": "few_shots_AND_grammar",
                    "test_generation_strategy": "few_shot",
                    "seed": 1,
                    "pipeline_variant": "full",
                    "provenance": build_provenance("etl", "Tree2Graph"),
                },
            )
            manifest = run_store.read_manifest(paths)
            assert manifest is not None
            initial = paths.generation_response(
                "transformation-generation", 0, "Tree2Graph.etl"
            )
            initial.parent.mkdir(parents=True, exist_ok=True)
            initial.write_text("rule Initial {}\n", encoding="utf-8")
            run_store.record_generation(
                paths,
                manifest,
                artifact_type="transformation",
                iteration=0,
                purpose="initial",
                provider="openai",
                model="gpt-5",
                strategy="few_shots_AND_grammar",
            )
            run_store.record_attempt(
                paths,
                "syntax-validation",
                {
                    "schema_version": "2.0",
                    "status": "failed",
                    "outcome_code": "SYNTAX_INVALID",
                },
                evidence={"details": {"parser_diagnostics": ["bad syntax"]}},
            )
            run_store.prepare_refinement(
                paths,
                manifest,
                artifact_type="transformation",
                iteration=1,
                previous_iteration=0,
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                reason="SYNTAX_INVALID",
                diagnoses_root=root / "diagnoses",
            )
            refined = paths.generation_response(
                "transformation-generation", 1, "Tree2Graph.etl"
            )
            refined.parent.mkdir(parents=True, exist_ok=True)
            refined.write_text("rule Refined {}\n", encoding="utf-8")
            run_store.record_generation(
                paths,
                manifest,
                artifact_type="transformation",
                iteration=1,
                purpose="syntax_refinement",
                provider="anthropic",
                model="claude-sonnet-4-20250514",
                strategy="few_shots_AND_grammar",
            )
            generation_reference = paths.generation_record(
                "transformation", 1
            ).relative_to(paths.root).as_posix()
            run_store.record_attempt(
                paths,
                "syntax-validation",
                {
                    "schema_version": "2.0",
                    "status": "passed",
                    "outcome_code": "SYNTAX_VALID",
                    "artifacts": {
                        "transformation_generation_record": generation_reference
                    },
                },
            )

            aggregate = aggregate_stage(root, ["attribution-1"], "syntax-validation")

            self.assertIn(
                "full/gpt-5/few_shots_AND_grammar/gpt-5/few_shot",
                aggregate["by_group"],
            )
            generation_group = aggregate["by_generation"][0]
            self.assertEqual(
                "gpt-5",
                generation_group["configured"]["transformation_model_family"],
            )
            responsible = generation_group["responsible_generations"]["transformation"]
            self.assertEqual(1, responsible["artifact_iteration"])
            self.assertEqual("anthropic", responsible["provider"])
            self.assertEqual("claude-sonnet-4-20250514", responsible["model"])
            self.assertTrue(generation_group["generation_provenance_complete"])
            self.assertEqual({"SYNTAX_VALID": 1}, generation_group["outcomes"])


class SignificanceTests(unittest.TestCase):
    def test_contingency_cells_preserve_pair_ordering(self) -> None:
        result = mcnemar(
            [True, True, False, False],
            [True, False, True, False],
        )

        self.assertEqual(1, result["both_pass"])
        self.assertEqual(1, result["baseline_only"])
        self.assertEqual(1, result["variant_only"])
        self.assertEqual(1, result["both_fail"])
        self.assertEqual(1.0, result["p_value"])

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

    def test_mismatched_pairs_are_rejected(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "paired samples must have equal length",
        ):
            mcnemar([True], [])


if __name__ == "__main__":
    unittest.main()
