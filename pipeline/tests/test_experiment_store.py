from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm4mtl import experiment_store
from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.manifest import ManifestExistsError


class ExperimentStoreTests(unittest.TestCase):

    def test_create_index_and_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = experiment_store.create_experiment(
                Path(temp_dir),
                "exp-1",
                {"variant": "full", "matrix": "thesis-ablation"},
            )
            manifest = experiment_store.read_manifest(paths)
            self.assertEqual("exp-1", manifest["experiment_id"])
            self.assertEqual("full", manifest["variant"])

            experiment_store.add_run(paths, "run-a")
            experiment_store.add_run(paths, "run-b")
            experiment_store.add_run(paths, "run-a")  # idempotent
            self.assertEqual(["run-a", "run-b"], experiment_store.list_runs(paths))

            with self.assertRaises(ManifestExistsError):
                experiment_store.create_experiment(Path(temp_dir), "exp-1", {})

    def test_concurrent_index_updates_do_not_lose_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = experiment_store.create_experiment(
                Path(temp_dir), "exp-concurrent", {}
            )
            run_ids = [f"run-{index}" for index in range(32)]

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(
                    pool.map(
                        lambda run_id: experiment_store.add_run(paths, run_id), run_ids
                    )
                )

            self.assertEqual(set(run_ids), set(experiment_store.list_runs(paths)))
            validate_artifact(
                "run-index",
                {
                    "schema_version": experiment_store.SCHEMA_VERSION,
                    "runs": experiment_store.list_runs(paths),
                },
            )


if __name__ == "__main__":
    unittest.main()
