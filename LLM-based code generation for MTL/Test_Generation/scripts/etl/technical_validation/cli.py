"""CLI for technical validation of extracted generated ETL suites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.paths import default_etl_test_dir, default_generated_tests_root, default_results_root
from etl.suites.discovery import discover_suites
from etl.technical_validation.results import write_results
from etl.technical_validation.suite import check_suite


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
        default=default_generated_tests_root(),
        help="Root containing <task>/candidates/<llm>/<strategy>/<suite_id>.",
    )
    parser.add_argument(
        "--etl-test-dir",
        type=Path,
        default=default_etl_test_dir(),
        help="ETL_Test Maven project directory.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=default_results_root(),
        help="Root where per-task technical validation CSV files are written.",
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
    suites = discover_suites(args)
    if not suites:
        task = args.task or "*"
        print(f"No candidate suites found for task {task}", file=sys.stderr)
        return 1

    if args.dry_run:
        for suite in suites:
            print(f"Would check {suite.path}")
        return 0

    rows: list[dict[str, str]] = []
    for suite in suites:
        print(f"Checking {suite.task} | {suite.llm} | {suite.strategy} | {suite.suite_id}")
        row = check_suite(suite, args)
        rows.append(row)
        print(
            "  technically_valid="
            f"{row['technically_valid']} contract_valid={row['contract_valid']} "
            f"compiles={row['compiles']} models_load={row['models_load']} "
            f"junit_executes={row['junit_executes']}"
        )
        if row["error_summary"]:
            print(f"  error: {row['error_summary']}")

    write_results(rows, args)
    failed = sum(1 for row in rows if row["technically_valid"] != "True")
    return 0 if failed == 0 else 1
