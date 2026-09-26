"""Command-line options shared by the CLIs that run generated ETL suites.

Technical validation and reference validation select and run suites the same
way, so their common options are defined once here.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from llm4mtl.conventions import (
    ETL_CONFIG,
    default_generated_tests_root,
    default_results_root,
    default_test_project_dir,
)


def add_suite_selection_arguments(
    parser: argparse.ArgumentParser, *, verb: str
) -> None:
    """Add the options that choose suites: ``--suite``, ``--task``, and the root.

    ``verb`` names what the CLI does with a suite, for example ``check``.
    """
    parser.add_argument(
        "--suite",
        action="append",
        type=Path,
        help=f"Specific candidate suite directory to {verb}. Can be repeated.",
    )
    parser.add_argument(
        "--task",
        help=f"Only {verb} suites for this task, e.g. Tree2Graph.",
    )
    parser.add_argument(
        "--generated-tests-root",
        type=Path,
        default=default_generated_tests_root(ETL_CONFIG),
        help="Root containing <task>/candidates/<llm>/<strategy>/<suite_id>.",
    )


def add_suite_run_arguments(
    parser: argparse.ArgumentParser, *, results_name: str, timeout_seconds: int
) -> None:
    """Add the options for running suites in Maven and writing their CSV results.

    ``results_name`` names the CSV files in the help text. ``timeout_seconds`` is
    the default Maven timeout.
    """
    parser.add_argument(
        "--etl-test-dir",
        type=Path,
        default=default_test_project_dir(ETL_CONFIG),
        help="ETL_Test Maven project directory.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=default_results_root(ETL_CONFIG),
        help=f"Root where per-task {results_name} CSV files are written.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=timeout_seconds,
        help="Maven command timeout in seconds.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSV files instead of overwriting them.",
    )
