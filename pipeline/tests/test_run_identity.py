"""A run is one combination, and it stays the one it was created with.

Two failures this guards against. A run that leaves an identity axis open used
to make its stages select every known value, so results were attributed to a run
id that did not describe them. And a manifest that could be rewritten would
re-label evidence produced under the earlier identity.
"""

from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from llm4mtl.provenance import build_provenance
from llm4mtl.run_store import create_run
from llm4mtl.run_store.identity import InvalidRunIdError
from llm4mtl.stages.dispatch import prepare_workspace
from llm4mtl.stages.models import ConfigError
from llm4mtl.stages.selection import fixed_selection

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


class ProvenanceTests(unittest.TestCase):

    def test_provenance_names_the_inputs_the_run_depends_on(self) -> None:
        provenance = build_provenance("etl", "Tree2Graph")
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


class RunDirectoryContainmentTests(unittest.TestCase):

    def test_a_traversing_run_id_writes_nothing_before_it_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs = Path(temp_dir) / "runs"
            runs.mkdir()

            with self.assertRaises(InvalidRunIdError):
                create_run(runs, "../escaped", IDENTITY)

            self.assertFalse((Path(temp_dir) / "escaped").exists())
            self.assertEqual([], list(runs.iterdir()))


class WorkspaceIsolationTests(unittest.TestCase):

    def test_workspace_is_materialized_once_inside_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source-harness"
            source.mkdir()
            (source / "pom.xml").write_text("<project/>\n", encoding="utf-8")
            run_dir = root / "runs" / "run-001"
            run_dir.mkdir(parents=True)

            with patch(
                "llm4mtl.stages.dispatch.default_test_project_dir",
                return_value=source,
            ):
                with ThreadPoolExecutor(max_workers=4) as pool:
                    destinations = list(
                        pool.map(
                            lambda _: prepare_workspace(run_dir, "etl"),
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
