from __future__ import annotations

import json
import unittest

from llm4mtl.conventions import repo_root
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.paths import MIGRATION_MAP, REPO_ROOT, TARGET


class ActivePathTests(unittest.TestCase):
    def test_active_runtime_uses_existing_repository_root(self) -> None:
        self.assertEqual(REPO_ROOT, repo_root())
        self.assertEqual(REPO_ROOT, ExperimentOrchestrator().repo_root)
        self.assertTrue(REPO_ROOT.is_dir())

    def test_target_layout_matches_migrated_directories(self) -> None:
        self.assertEqual(REPO_ROOT / "prompt_assets", TARGET.prompt_assets)
        self.assertTrue(TARGET.prompt_assets.is_dir())
        self.assertEqual(
            TARGET.package / "transformation_execution",
            MIGRATION_MAP["pipeline/transformation_validation"][1],
        )
        self.assertEqual(TARGET.workflows / "tests", MIGRATION_MAP["n8n/tests"][1])


class N8nWorkflowTests(unittest.TestCase):
    def test_connections_reference_existing_nodes(self) -> None:
        for workflow in sorted(TARGET.workflows.rglob("*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "nodes" not in payload:
                continue
            names = {node["name"] for node in payload["nodes"]}
            connections = payload.get("connections", {})
            sources = set(connections)
            targets: set[str] = set()
            self._collect_connection_targets(connections, targets)
            with self.subTest(workflow=workflow):
                self.assertLessEqual(sources | targets, names)

    def test_test_generation_model_mount_preserves_language_directory(self) -> None:
        compose = TARGET.workflows / "tests" / "docker-compose.yml"
        text = compose.read_text(encoding="utf-8")
        self.assertIn('"../../../benchmark/metamodels:/data/models:ro"', text)
        self.assertTrue((REPO_ROOT / "benchmark" / "metamodels" / "etl").is_dir())

    @classmethod
    def _collect_connection_targets(cls, value: object, result: set[str]) -> None:
        if isinstance(value, dict):
            node = value.get("node")
            if isinstance(node, str):
                result.add(node)
            for nested in value.values():
                cls._collect_connection_targets(nested, result)
        elif isinstance(value, list):
            for nested in value:
                cls._collect_connection_targets(nested, result)


if __name__ == "__main__":
    unittest.main()
