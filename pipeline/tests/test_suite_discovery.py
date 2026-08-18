"""Candidate-suite discovery preserves selection and deterministic ordering."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from llm4mtl.semantic_tests.suites.discovery import discover_suites


class SuiteDiscoveryTests(unittest.TestCase):
    def test_discovered_suites_are_sorted_and_must_be_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected_paths = [
                root
                / "TaskA/candidates/model/strategy/etl-tree2graph-20260818-133432-000",
                root / "TaskA/candidates/model/strategy/suite_001",
                root / "TaskA/candidates/model/strategy/suite_002",
                root / "TaskB/candidates/model/strategy/suite_003",
            ]
            for path in reversed(expected_paths):
                path.mkdir(parents=True)
            ignored_file = root / "TaskA/candidates/model/strategy/suite_file"
            ignored_file.write_text("not a suite directory", encoding="utf-8")
            (root / "TaskWithoutCandidates").mkdir()
            args = argparse.Namespace(
                suite=[],
                generated_tests_root=root,
                task=None,
            )

            suites = discover_suites(args, "etl")

            self.assertEqual(
                [path.resolve() for path in expected_paths],
                [suite.path for suite in suites],
            )
            self.assertEqual(
                ["TaskA", "TaskA", "TaskA", "TaskB"],
                [suite.task for suite in suites],
            )

    def test_explicit_suites_preserve_input_order_and_ignore_task_filter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "TaskA/candidates/model/strategy/suite_001"
            second = root / "TaskB/candidates/model/strategy/suite_002"
            first.mkdir(parents=True)
            second.mkdir(parents=True)
            args = argparse.Namespace(
                suite=[second, first],
                generated_tests_root=root,
                task="TaskA",
            )

            suites = discover_suites(args, "qvto")

            self.assertEqual(
                [second.resolve(), first.resolve()],
                [suite.path for suite in suites],
            )
            self.assertEqual(["TaskB", "TaskA"], [suite.task for suite in suites])
            self.assertEqual(["qvto", "qvto"], [suite.language for suite in suites])


if __name__ == "__main__":
    unittest.main()
