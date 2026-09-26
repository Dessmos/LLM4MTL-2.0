"""Candidate-suite discovery preserves selection and deterministic ordering."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from llm4mtl.semantic_tests.suites.discovery import (
    CandidateIdentity,
    SuiteIdentityError,
    candidate_identity,
    discover_suites,
    suite_from_path,
)
from llm4mtl.semantic_tests.suites.java import JavaSourceError, infer_fqcn


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



class CandidateIdentityTests(unittest.TestCase):

    def test_the_identity_is_read_off_the_last_five_path_parts(self) -> None:
        cases = (
            Path("/root/Tree2Graph/candidates/gpt-5/few_shot/suite_001"),
            Path("Tree2Graph/candidates/gpt-5/few_shot/suite_001"),
        )
        for path in cases:
            with self.subTest(path=str(path)):
                self.assertEqual(
                    CandidateIdentity(
                        task="Tree2Graph",
                        llm="gpt-5",
                        strategy="few_shot",
                        suite_id="suite_001",
                    ),
                    candidate_identity(path),
                )

    def test_other_layouts_are_rejected(self) -> None:
        cases = (
            Path("candidates/gpt-5/few_shot/suite_001"),
            Path("/root/Tree2Graph/validated/gpt-5/few_shot/suite_001"),
            Path("/root/Tree2Graph/candidates/gpt-5/few_shot"),
        )
        for path in cases:
            with self.subTest(path=str(path)):
                with self.assertRaisesRegex(ValueError, "not a candidate suite"):
                    candidate_identity(path)


class SuiteIdentityFailureTests(unittest.TestCase):
    """Unreadable identities are domain errors a caller can catch, not process exits."""

    def test_a_path_outside_the_candidate_layout_names_no_suite(self) -> None:
        with self.assertRaisesRegex(SuiteIdentityError, "Cannot infer"):
            suite_from_path(Path("/not/a/suite"), "etl")

    def test_a_java_source_without_a_class_names_no_test(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            java = Path(temp_dir) / "Empty.java"
            java.write_text("package generated;\n", encoding="utf-8")
            with self.assertRaisesRegex(JavaSourceError, "Empty.java"):
                infer_fqcn(java)


if __name__ == "__main__":
    unittest.main()
