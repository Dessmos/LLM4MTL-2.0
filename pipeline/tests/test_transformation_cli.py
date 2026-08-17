"""Behavior tests for the generated-transformation validation CLI."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from llm4mtl.transformation_execution import cli
from llm4mtl.transformation_execution.models import (
    GeneratedTransformation,
    ValidatedSuite,
    ValidationPair,
)


def _args(*, dry_run: bool) -> argparse.Namespace:
    return argparse.Namespace(
        validated_tests_root=Path("validated"),
        observations_root=Path("observations"),
        suite=None,
        task=None,
        test_model=None,
        test_strategy=None,
        transformations_root=Path("transformations"),
        transformation=None,
        transformation_model=None,
        transformation_strategy=None,
        dry_run=dry_run,
        etl_test_dir=Path("engine-template"),
        artifacts_root=Path("artifacts"),
        results_root=Path("results"),
        timeout=240,
        overwrite_results=False,
    )


def _pair() -> ValidationPair:
    return ValidationPair(
        suite=ValidatedSuite(
            path=Path("suite"),
            task="Tree2Graph",
            llm="gpt-5",
            strategy="few_shot",
            suite_id="suite_001",
        ),
        transformation=GeneratedTransformation(
            path=Path("Tree2Graph.etl"),
            task="Tree2Graph",
            llm="claude-sonnet-4",
            strategy="grammar",
        ),
    )


class TransformationCliTests(unittest.TestCase):
    def test_missing_suite_error_keeps_precedence_over_other_empty_selections(self) -> None:
        stderr = StringIO()
        with patch.object(cli, "parse_args", return_value=_args(dry_run=False)):
            with patch.object(cli, "discover_validated_suites", return_value=[]):
                with patch.object(cli, "discover_transformations", return_value=[]):
                    with redirect_stderr(stderr):
                        exit_code = cli.main([])

        self.assertEqual(1, exit_code)
        self.assertEqual(
            "No validated suites matched the selection.\n",
            stderr.getvalue(),
        )

    def test_dry_run_prints_pairs_without_materializing_an_engine(self) -> None:
        pair = _pair()
        stdout = StringIO()
        with patch.object(cli, "parse_args", return_value=_args(dry_run=True)):
            with patch.object(
                cli,
                "discover_validated_suites",
                return_value=[pair.suite],
            ):
                with patch.object(
                    cli,
                    "discover_transformations",
                    return_value=[pair.transformation],
                ):
                    with patch.object(cli, "match_pairs", return_value=[pair]):
                        with patch.object(cli, "materialize_engine") as materialize:
                            with redirect_stdout(stdout):
                                exit_code = cli.main([])

        self.assertEqual(0, exit_code)
        self.assertEqual(
            "Would validate Tree2Graph.etl with suite\n",
            stdout.getvalue(),
        )
        materialize.assert_not_called()

    def test_execution_archives_results_and_preserves_failure_exit_code(self) -> None:
        pair = _pair()
        args = _args(dry_run=False)
        archived = SimpleNamespace(
            status="failed",
            compiles=True,
            executes=True,
            tests_pass=False,
            error_summary="assertion failed",
            artifact_dir="artifacts/pair",
        )
        stdout = StringIO()

        with patch.object(cli, "materialize_engine", return_value=Path("engine")):
            with patch.object(cli, "validate_pair", return_value=object()) as validate:
                with patch.object(cli, "archive_result", return_value=archived):
                    with patch.object(
                        cli,
                        "write_results",
                        return_value=[Path("results/report.csv")],
                    ) as write:
                        with redirect_stdout(stdout):
                            exit_code = cli._execute_pairs(args, [pair])

        self.assertEqual(1, exit_code)
        validate.assert_called_once_with(pair, Path("engine"), 240)
        write.assert_called_once_with([archived], Path("results"), append=True)
        self.assertIn("error: assertion failed", stdout.getvalue())
        self.assertIn("Wrote results/report.csv", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
