from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm4mtl.paths import REPO_ROOT


sys.path.insert(0, str(REPO_ROOT))

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    preflight_runs,
)
from evaluation.calculate_metrics import (
    _aggregate_heldout_metrics,
    _coverage_metrics,
    _heldout_counts,
    _mutation_metrics,
    _suite_counts,
)
from evaluation.coverage.calculate_coverage import (
    MetamodelShape,
    covered_eclasses,
)
from evaluation.heldout.run_heldout import classify_surefire_cases
from evaluation.mutation.generate_mutants import generate_mutants
from llm4mtl.domain import RawExecutionEvidence, SurefireArtifact
from llm4mtl.task_contracts import ModelContract


EXPERIMENT_CONFIG = {
    "max_test_refinement_iterations": 1,
    "max_transformation_refinement_iterations": 1,
    "parser_feedback": True,
    "semantic_feedback": True,
    "source_diagnosis": True,
}


class EvaluationPreflightTests(unittest.TestCase):

    def test_preflight_rejects_entire_selection_without_experiment_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "controlled")
            _write_run(root, "legacy", experiment_config=None)
            run_ids = root / "runs.txt"
            run_ids.write_text("controlled\nlegacy\n", encoding="utf-8")

            with self.assertRaisesRegex(
                EvaluationInputError,
                "legacy: manifest experiment_config is missing",
            ):
                preflight_runs(root / "runs", run_ids)

    def test_preflight_accepts_contiguous_stored_iterations_within_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "run-1", final_iteration=1)
            run_ids = root / "runs.txt"
            run_ids.write_text("run-1\n", encoding="utf-8")

            selected = preflight_runs(root / "runs", run_ids)

            self.assertEqual(("run-1",), tuple(run.run_id for run in selected))


class HeldoutEvidenceTests(unittest.TestCase):

    def test_surefire_cases_map_back_to_stable_semantic_ids(self) -> None:
        xml = """<testsuite tests="3" failures="1" errors="1">
          <testcase name="h001"/>
          <testcase name="repairEdge"><failure message="wrong count"/></testcase>
          <testcase name="h003"><error message="engine failed"/></testcase>
        </testsuite>"""
        evidence = RawExecutionEvidence(
            exit_code=1,
            timed_out=False,
            stdout="",
            stderr="",
            reports_present=True,
            reports=(SurefireArtifact("TEST-heldout.xml", xml),),
        )

        statuses = classify_surefire_cases(
            evidence,
            ("H001", "repair_edge", "H003", "H004"),
        )

        self.assertEqual(
            {
                "H001": "PASS",
                "repair_edge": "FAIL",
                "H003": "ERROR",
                "H004": "NOT_RUN",
            },
            statuses,
        )


class MutationToolTests(unittest.TestCase):

    def test_generator_applies_one_deterministic_change_and_leaves_qualification_blank(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "mutants"
            specification = {
                "operator_set_version": "etl-minimal-v1",
                "mutants": [
                    {
                        "mutant_id": "M001",
                        "language": "etl",
                        "task": "Tree2Graph",
                        "operator": "rename_rule",
                        "find": "rule Tree2Node",
                        "replacement": "rule Tree2NodeMutated",
                    }
                ],
            }

            rows = generate_mutants(specification, output)

            self.assertEqual(1, len(rows))
            mutant = output / "etl" / "Tree2Graph" / "M001.etl"
            self.assertTrue(mutant.is_file())
            self.assertIn("rule Tree2NodeMutated", mutant.read_text(encoding="utf-8"))
            self.assertEqual("", rows[0]["qualified"])
            self.assertNotEqual(rows[0]["source_hash"], rows[0]["mutant_hash"])

    def test_qualified_and_incremental_scores_use_only_mq(self) -> None:
        catalog = [
            {"mutant_id": "M1", "qualified": "true"},
            {"mutant_id": "M2", "qualified": "true"},
            {"mutant_id": "M3", "qualified": "false"},
        ]
        observations = [
            {"mutant_id": "M1", "test_source": "baseline", "killed": "true"},
            {"mutant_id": "M1", "test_source": "generated", "killed": "true"},
            {"mutant_id": "M2", "test_source": "baseline", "killed": "false"},
            {"mutant_id": "M2", "test_source": "generated", "killed": "true"},
            {"mutant_id": "M3", "test_source": "generated", "killed": "true"},
        ]

        metrics = {
            row["metric"]: row for row in _mutation_metrics(catalog, observations)
        }

        self.assertEqual(1.0, metrics["qualified_mutation_score"]["value"])
        self.assertEqual(0.5, metrics["incremental_mutation_score"]["value"])


class CoverageEvaluationTests(unittest.TestCase):

    def test_coverage_counts_nested_input_instances_and_reaction_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            suite = Path(temporary)
            models = suite / "models"
            models.mkdir()
            (models / "tree.xmi").write_text(
                """<?xml version="1.0"?>
                <Tree:Tree xmlns:Tree="Tree"><children/></Tree:Tree>""",
                encoding="utf-8",
            )
            input_contracts = {
                "Tree": ModelContract(
                    runtime_name="Tree",
                    roles=("inout",),
                    kind="emf",
                    metamodel_uri="Tree",
                    metamodel_ns_prefix="Tree",
                    metamodel_alias="Tree",
                    metamodel_file=None,
                    types_used_in_transformation=("Tree", "Leaf"),
                    available_types=("Tree", "Leaf"),
                )
            }
            semantic_cases = {
                "tests": [
                    {
                        "models": [
                            {
                                "name": "Tree",
                                "role": "inout",
                                "path": "models/tree.xmi",
                            }
                        ],
                        "changes": [
                            {
                                "kind": "create",
                                "target": {"slot": "Tree", "type": "Tree"},
                                "value": {"type": "Leaf"},
                            }
                        ],
                    }
                ]
            }

            covered = covered_eclasses(
                semantic_cases,
                suite,
                input_contracts,
                {"Tree": MetamodelShape({"Tree": {"children": "Tree"}})},
                "reactions",
            )

            self.assertEqual({"Tree", "Leaf"}, covered)


class MetricAggregationTests(unittest.TestCase):

    def test_heldout_metrics_compare_only_t0_to_final(self) -> None:
        runs = (_selected_run("R1"), _selected_run("R2"))
        heldout = [
            _heldout("R1", 0, "H1", "PASS"),
            _heldout("R1", 0, "H2", "FAIL"),
            _heldout("R1", 1, "H1", "PASS"),
            _heldout("R1", 1, "H2", "FAIL"),
            _heldout("R1", 2, "H1", "PASS"),
            _heldout("R1", 2, "H2", "PASS"),
            _heldout("R2", 0, "H1", "PASS"),
            _heldout("R2", 0, "H2", "PASS"),
            _heldout("R2", 1, "H1", "FAIL"),
            _heldout("R2", 1, "H2", "PASS"),
        ]

        counts = _heldout_counts(runs, heldout)
        aggregate = {row["metric"]: row for row in _aggregate_heldout_metrics(counts)}

        self.assertEqual(0.5, aggregate["heldout_semantic_pass_rate"]["value"])
        self.assertEqual(1.0, aggregate["heldout_repair_success_rate"]["value"])
        self.assertEqual(1 / 3, aggregate["regression_rate"]["value"])

    def test_suite_level_er_and_rpr_do_not_count_missing_execution_as_executable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = _selected_run("R1", root / "run")
            generated = root / "generated"
            for suite_id in ("R1_000", "R1_001"):
                suite = (
                    generated / "Task" / "candidates" / "model" / "strategy" / suite_id
                )
                suite.mkdir(parents=True)
                (suite / "metadata.json").write_text(
                    json.dumps(
                        {
                            "suite_id": suite_id,
                            "language": "etl",
                            "task": "Task",
                        }
                    ),
                    encoding="utf-8",
                )
            observation = (
                run.root
                / "observations"
                / "Task"
                / "model"
                / "strategy"
                / "R1_000"
                / "suite_execution.json"
            )
            observation.parent.mkdir(parents=True)
            observation.write_text(
                json.dumps(
                    {
                        "suite_id": "R1_000",
                        "inputs": {
                            "transformation": {"role": "reference_transformation"}
                        },
                        "observation": {
                            "technically_executable": True,
                            "reference_valid": True,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "evaluation.calculate_metrics.default_generated_tests_root",
                return_value=generated,
            ):
                executable, reference_pass, total = _suite_counts(run)

            self.assertEqual((1, 1, 2), (executable, reference_pass, total))

    def test_coverage_metric_unions_suite_classes_within_one_run(self) -> None:
        run = _selected_run("R1")
        rows = [
            {
                "run_id": "R1",
                "covered_eclasses": "A",
                "eligible_eclasses": "A;B;C",
            },
            {
                "run_id": "R1",
                "covered_eclasses": "B",
                "eligible_eclasses": "A;B;C",
            },
        ]

        metric = _coverage_metrics((run,), rows)[0]

        self.assertEqual(2, metric["numerator"])
        self.assertEqual(3, metric["denominator"])
        self.assertEqual(2 / 3, metric["value"])


def _write_run(
    root: Path,
    run_id: str,
    *,
    experiment_config: dict[str, object] | None = EXPERIMENT_CONFIG,
    final_iteration: int = 0,
) -> None:
    run_root = root / "runs" / run_id
    run_root.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "language": "etl",
        "task": "Tree2Graph",
        "pipeline_variant": "full",
    }
    if experiment_config is not None:
        manifest["experiment_config"] = experiment_config
    (run_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_root / "result.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "completed",
                "terminal_state": "SEMANTIC_PASSED",
                "recorded_at": "2026-01-01T00:00:00+00:00",
                "transformation_iteration": final_iteration,
            }
        ),
        encoding="utf-8",
    )
    for iteration in range(final_iteration + 1):
        directory = run_root / "transformation" / f"iteration-{iteration:03d}"
        directory.mkdir(parents=True)
        transformation = directory / "Tree2Graph.etl"
        transformation.write_text(f"// iteration {iteration}\n", encoding="utf-8")
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "language": "etl",
                    "task": "Tree2Graph",
                    "iteration": iteration,
                    "transformations": [
                        {
                            "path": str(transformation),
                            "sha256": hashlib.sha256(
                                transformation.read_bytes()
                            ).hexdigest(),
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )


def _selected_run(run_id: str, root: Path | None = None) -> SelectedRun:
    manifest = {
        "run_id": run_id,
        "language": "etl",
        "task": "Task",
        "pipeline_variant": "full",
        "experiment_config": EXPERIMENT_CONFIG,
    }
    return SelectedRun(
        run_id,
        root or Path("/tmp") / run_id,
        manifest,
        {"run_id": run_id},
    )


def _heldout(run_id: str, iteration: int, test_id: str, result: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "iteration": str(iteration),
        "test_id": test_id,
        "result": result,
    }


if __name__ == "__main__":
    unittest.main()
