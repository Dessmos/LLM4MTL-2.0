"""A run is one combination, and it stays the one it was created with.

Two failures this guards against. A run that leaves an identity axis open used
to make its stages select every known value, so results were attributed to a run
id that did not describe them. And a manifest that could be rewritten would
re-label evidence produced under the earlier identity.
"""

from __future__ import annotations

import tempfile
import unittest
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from llm4mtl.experiment_runner.adapters.base import fixed_selection
from llm4mtl.experiment_runner.config import ConfigError, validate_config
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.experiment_runner.orchestrator import (
    ExperimentOrchestrator,
    exactly_one,
    reject_identity_drift,
    run_identity,
)
from llm4mtl.provenance import build_provenance
from llm4mtl.run_store import ManifestExistsError, create_run, write_manifest
from llm4mtl.run_store.identity import InvalidRunIdError

IDENTITY = {
    "language": "etl",
    "task": "Tree2Graph",
    "transformation_model": "gpt-5",
    "test_generation_model": "gpt-5",
    "transformation_strategy": "grammar",
    "test_generation_strategy": "few_shot",
    "seed": 1,
    "pipeline_variant": "full",
    "provenance": build_provenance("etl", "Tree2Graph"),
}


def config(**overrides: object) -> PipelineConfig:
    base = dict(
        language="etl",
        tasks=["Tree2Graph"],
        test_models=["gpt-5"],
        test_strategies=["few_shot"],
        transformation_models=["gpt-5"],
    )
    base.update(overrides)
    return PipelineConfig(**base)


class IdentityAxisTests(unittest.TestCase):
    def test_several_values_on_one_axis_are_refused(self) -> None:
        with self.assertRaises(ConfigError):
            exactly_one("test-generation model", ["gpt-5", "claude-sonnet-4"], required=False)

    def test_an_axis_no_stage_uses_is_recorded_as_not_applicable(self) -> None:
        # Null means "not applicable to this run", never "any value".
        identity = run_identity(config(transformation_models=[]), "hash")
        self.assertIsNone(identity["transformation_model"])
        self.assertEqual("gpt-5", identity["test_generation_model"])

    def test_the_task_must_always_be_fixed(self) -> None:
        with self.assertRaises(ConfigError):
            run_identity(config(tasks=[]), "hash")

    def test_all_tasks_must_be_expanded_before_a_run_is_created(self) -> None:
        with self.assertRaises(ConfigError):
            validate_config(config(tasks=[], all_tasks=True))

    def test_test_and_transformation_strategies_are_distinct_identity_axes(self) -> None:
        identity = run_identity(
            config(transformation_strategies=["grammar"]),
            "hash",
        )
        self.assertEqual("few_shot", identity["test_generation_strategy"])
        self.assertEqual("grammar", identity["transformation_strategy"])

    def test_provenance_names_the_inputs_the_run_depends_on(self) -> None:
        provenance = run_identity(config(), "hash")["provenance"]
        self.assertIn("git_commit", provenance)
        self.assertEqual("2.5.0", provenance["tool_versions"]["epsilon"])
        hashes = provenance["input_hashes"]
        self.assertEqual(64, len(hashes["reference_transformation"]))
        self.assertEqual(64, len(hashes["task_contract"]))
        self.assertEqual(64, len(hashes["task_prompt"]))
        self.assertEqual(
            {
                "benchmark/metamodels/additional_models/ETL_model/Graph.ecore",
                "benchmark/metamodels/additional_models/ETL_model/Tree.ecore",
            },
            set(hashes["metamodels"]),
        )


class SelectionTests(unittest.TestCase):
    def test_a_stage_refuses_to_select_every_value(self) -> None:
        with self.assertRaises(ConfigError) as raised:
            fixed_selection("test-generation model", [])
        self.assertIn("every value", str(raised.exception))

    def test_an_explicit_selection_is_used_as_given(self) -> None:
        self.assertEqual({"gpt-5"}, fixed_selection("test-generation model", ["gpt-5"]))


class ManifestImmutabilityTests(unittest.TestCase):
    def test_a_manifest_can_never_be_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = create_run(Path(temp_dir), "run_001", IDENTITY)
            with self.assertRaises(ManifestExistsError):
                write_manifest(paths, {"run_id": "run_001", **IDENTITY})

    def test_re_entering_a_run_under_another_identity_is_refused(self) -> None:
        stored = {"run_id": "run_001", **IDENTITY}
        with self.assertRaises(ConfigError) as raised:
            reject_identity_drift(stored, {**IDENTITY, "task": "OO2DB"}, "run_001")
        self.assertIn("task", str(raised.exception))

    def test_the_same_identity_may_re_enter_its_run(self) -> None:
        reject_identity_drift({"run_id": "run_001", **IDENTITY}, dict(IDENTITY), "run_001")

    def test_rejected_resume_does_not_overwrite_the_resolved_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ExperimentOrchestrator()
            runner.runs_root = Path(temp_dir) / "runs"
            runner.runs_root.mkdir()
            original = config(run_id="same", command="tests.extract")
            paths = create_run(runner.runs_root, "same", run_identity(original, "original"))
            paths.root.joinpath("config.resolved.yaml").write_text(
                json.dumps({"task": "original"}),
                encoding="utf-8",
            )

            changed = config(
                tasks=["OO2DB"],
                run_id="same",
                command="tests.extract",
                resume=True,
            )
            with self.assertRaises(ConfigError):
                runner.run(changed)

            self.assertEqual(
                {"task": "original"},
                json.loads(
                    paths.root.joinpath("config.resolved.yaml").read_text(encoding="utf-8")
                ),
            )


class RunDirectoryContainmentTests(unittest.TestCase):
    def test_a_traversing_run_id_writes_nothing_before_it_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = ExperimentOrchestrator()
            orchestrator.runs_root = Path(temp_dir) / "runs"
            orchestrator.runs_root.mkdir()

            with self.assertRaises(InvalidRunIdError):
                orchestrator.run(config(run_id="../escaped", command="tests.extract"))

            self.assertFalse((Path(temp_dir) / "escaped").exists())


class WorkspaceIsolationTests(unittest.TestCase):
    def test_workspace_is_materialized_once_inside_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source-harness"
            source.mkdir()
            (source / "pom.xml").write_text("<project/>\n", encoding="utf-8")
            run_dir = root / "runs" / "run-001"
            run_dir.mkdir(parents=True)
            orchestrator = ExperimentOrchestrator()

            with patch(
                "llm4mtl.conventions.default_test_project_dir",
                return_value=source,
            ):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    destinations = list(
                        pool.map(
                            lambda _: orchestrator.prepare_workspace(run_dir, "etl"),
                            range(4),
                        )
                    )

            self.assertEqual(1, len(set(destinations)))
            self.assertEqual(
                (run_dir / "workspaces" / "etl").resolve(),
                destinations[0],
            )
            self.assertEqual(
                "<project/>\n",
                destinations[0].joinpath("pom.xml").read_text(encoding="utf-8"),
            )
            self.assertFalse((source / ".llm4mtl-execution.lock").exists())


if __name__ == "__main__":
    unittest.main()
