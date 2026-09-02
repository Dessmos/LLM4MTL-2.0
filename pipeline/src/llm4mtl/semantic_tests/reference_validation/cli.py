"""CLI for reference validation of generated ETL semantic suites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm4mtl.conventions import (
    ETL_CONFIG,
    default_test_project_dir,
    default_generated_tests_root,
    default_references_root,
    default_results_root,
)
from llm4mtl.domain import GeneratedSuite
from llm4mtl.languages import language_adapter
from llm4mtl.semantic_tests.reference_validation.results import write_results
from llm4mtl.semantic_tests.reference_validation.runner import reference_row, validate_suite
from llm4mtl.semantic_tests.suites.discovery import discover_suites
from llm4mtl.semantic_tests.validation import REFERENCE_INVALID, ValidationContext, workspace_for
from llm4mtl.workspace import materialize_engine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generated ETL semantic suites against reference transformations."
    )
    parser.add_argument(
        "--suite",
        action="append",
        type=Path,
        help="Specific candidate suite directory to validate. Can be repeated.",
    )
    parser.add_argument(
        "--task",
        help="Only validate suites for this task, e.g. Tree2Graph.",
    )
    parser.add_argument(
        "--generated-tests-root",
        type=Path,
        default=default_generated_tests_root(ETL_CONFIG),
        help="Root containing <task>/candidates/<llm>/<strategy>/<suite_id>.",
    )
    parser.add_argument(
        "--etl-test-dir",
        type=Path,
        default=default_test_project_dir(ETL_CONFIG),
        help="ETL_Test Maven project directory.",
    )
    parser.add_argument(
        "--references-root",
        type=Path,
        default=default_references_root(ETL_CONFIG),
        help="Root containing reference <task>.etl files.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=default_results_root(ETL_CONFIG),
        help="Root where per-task reference-validation CSV files are written.",
    )
    parser.add_argument(
        "--observations-root",
        type=Path,
        required=True,
        help=(
            "Root holding THIS run's suite-execution observations. A recorded "
            "observation for the same suite and reference is reused instead of "
            "executing the harness a second time. Required: a shared default "
            "would let one run reuse another run's observation."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=240,
        help="Maven command timeout in seconds.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing CSV files instead of overwriting them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover suites, but do not inject files or run Maven.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suites = discover_suites(args, "etl")
    if not suites:
        task = args.task or "*"
        print(f"No candidate suites found for task {task}", file=sys.stderr)
        return 1

    if args.dry_run:
        for suite in suites:
            print(f"Would validate {suite.path}")
        return 0

    return _execute_suites(args, suites)


def _execute_suites(
    args: argparse.Namespace,
    suites: list[GeneratedSuite],
) -> int:
    """Execute reference validation and write its result rows."""

    engine_dir = materialize_engine(
        args.etl_test_dir,
        args.observations_root.resolve().parent / "workspaces",
        "etl",
    )
    context = ValidationContext(
        adapter=language_adapter("etl"),
        workspace=workspace_for(engine_dir, args.observations_root),
        timeout=args.timeout,
    )

    rows: list[dict[str, str]] = []
    for suite in suites:
        print(
            f"Validating {suite.task} | {suite.llm} | {suite.strategy} | {suite.suite_id}"
        )
        verdict = validate_suite(suite, context)
        row = reference_row(verdict)
        rows.append(row)
        print(
            f"  valid={row['valid']} compiles={row['compiles']} "
            f"executes={row['executes']} status={verdict.status}"
        )
        if verdict.error_summary:
            print(f"  error: {verdict.error_summary}")

    write_results(rows, args)
    invalid = sum(1 for row in rows if row["status"] == REFERENCE_INVALID)
    return 0 if invalid == 0 else 1
