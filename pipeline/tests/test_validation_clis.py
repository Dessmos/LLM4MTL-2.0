"""Behavior tests for technical- and reference-validation CLIs."""

from __future__ import annotations

import argparse
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm4mtl.domain import GeneratedSuite
from llm4mtl.semantic_tests.reference_validation import cli as reference_cli
from llm4mtl.semantic_tests.technical_validation import cli as technical_cli


def _args(*, dry_run: bool) -> argparse.Namespace:
    return argparse.Namespace(
        task="Tree2Graph",
        dry_run=dry_run,
        etl_test_dir=Path("engine-template"),
        observations_root=Path("run/observations"),
        timeout=240,
    )


SUITE = GeneratedSuite(
    language="etl",
    path=Path("suite"),
    task="Tree2Graph",
    llm="gpt-5",
    strategy="few_shot",
    suite_id="suite_001",
)


class ValidationCliSelectionTests(unittest.TestCase):

    def test_empty_selection_messages_and_exit_codes_are_preserved(self) -> None:
        cases = (
            (reference_cli, "No candidate suites found for task Tree2Graph\n"),
            (technical_cli, "No candidate suites found for task Tree2Graph\n"),
        )
        for module, expected in cases:
            with self.subTest(module=module.__name__):
                stderr = StringIO()
                with patch.object(
                    module, "parse_args", return_value=_args(dry_run=False)
                ):
                    with patch.object(module, "discover_suites", return_value=[]):
                        with redirect_stderr(stderr):
                            exit_code = module.main([])

                self.assertEqual(1, exit_code)
                self.assertEqual(expected, stderr.getvalue())

    def test_dry_run_prints_without_materializing_an_engine(self) -> None:
        cases = (
            (reference_cli, "Would validate suite\n"),
            (technical_cli, "Would check suite\n"),
        )
        for module, expected in cases:
            with self.subTest(module=module.__name__):
                stdout = StringIO()
                with patch.object(
                    module, "parse_args", return_value=_args(dry_run=True)
                ):
                    with patch.object(module, "discover_suites", return_value=[SUITE]):
                        with patch.object(module, "materialize_engine") as materialize:
                            with redirect_stdout(stdout):
                                exit_code = module.main([])

                self.assertEqual(0, exit_code)
                self.assertEqual(expected, stdout.getvalue())
                materialize.assert_not_called()


class ValidationCliExecutionTests(unittest.TestCase):

    def test_failed_verdicts_are_written_and_return_failure(self) -> None:
        cases = (
            (
                reference_cli,
                "validate_suite",
                "reference_row",
                {
                    "valid": "False",
                    "compiles": "True",
                    "executes": "True",
                    "status": reference_cli.REFERENCE_INVALID,
                },
            ),
            (
                technical_cli,
                "check_suite",
                "technical_row",
                {
                    "technically_valid": "False",
                    "assertions_passed": "False",
                    "status": "not_executable",
                    "error_summary": "validation failed",
                },
            ),
        )
        for module, validator_name, row_builder_name, row in cases:
            with self.subTest(module=module.__name__):
                args = _args(dry_run=False)
                verdict = SimpleNamespace(
                    status=row["status"],
                    error_summary="validation failed",
                )
                stdout = StringIO()
                with ExitStack() as stack:
                    stack.enter_context(
                        patch.object(
                            module, "materialize_engine", return_value=Path("engine")
                        )
                    )
                    stack.enter_context(
                        patch.object(module, "language_adapter", return_value=object())
                    )
                    stack.enter_context(
                        patch.object(module, "workspace_for", return_value=object())
                    )
                    validator = stack.enter_context(
                        patch.object(module, validator_name, return_value=verdict)
                    )
                    stack.enter_context(
                        patch.object(module, row_builder_name, return_value=row)
                    )
                    write = stack.enter_context(patch.object(module, "write_results"))
                    with redirect_stdout(stdout):
                        exit_code = module._execute_suites(args, [SUITE])

                self.assertEqual(1, exit_code)
                validator.assert_called_once()
                write.assert_called_once_with([row], args)
                self.assertIn("validation failed", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
