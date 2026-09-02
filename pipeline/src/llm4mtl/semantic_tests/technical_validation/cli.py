"""CLI for technical validation of extracted generated ETL suites."""

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
from llm4mtl.semantic_tests.suites.discovery import discover_suites
from llm4mtl.semantic_tests.technical_validation.results import write_results
from llm4mtl.semantic_tests.technical_validation.suite import check_suite, technical_row
from llm4mtl.semantic_tests.validation import ValidationContext, workspace_for
from llm4mtl.workspace import materialize_engine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check technical validity of extracted generated ETL test suites."
    )
    parser.add_argument(
        "--suite",
        action="append",
        type=Path,
        help="Specific suite directory to check. Can be repeated.",
    )
    parser.add_argument(
        "--task",
        help="Only check suites for this task, e.g. Tree2Graph.",
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
        help=(
            "Root containing reference <task>.etl files. The suite is executed "
            "against the reference, because executability is only meaningful "
            "relative to a known transformation."
        ),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=default_results_root(ETL_CONFIG),
        help="Root where per-task technical validation CSV files are written.",
    )
    parser.add_argument(
        "--observations-root",
        type=Path,
        required=True,
        help=(
            "Root where THIS run's suite-execution observations are recorded. "
            "Required: a shared default would let one run reuse another run's "
            "observation as its own evidence."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
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
        help="Discover suites and print what would be checked.",
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
            print(f"Would check {suite.path}")
        return 0

    return _execute_suites(args, suites)


def _execute_suites(
    args: argparse.Namespace,
    suites: list[GeneratedSuite],
) -> int:
    """Execute technical validation and write its result rows."""

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
            f"Checking {suite.task} | {suite.llm} | {suite.strategy} | {suite.suite_id}"
        )
        verdict = check_suite(suite, context)
        row = technical_row(verdict)
        rows.append(row)
        print(
            f"  technically_valid={row['technically_valid']} "
            f"assertions_passed={row['assertions_passed']} status={row['status']}"
        )
        if row["error_summary"]:
            print(f"  error: {row['error_summary']}")

    write_results(rows, args)
    failed = sum(1 for row in rows if row["technically_valid"] != "True")
    return 0 if failed == 0 else 1
