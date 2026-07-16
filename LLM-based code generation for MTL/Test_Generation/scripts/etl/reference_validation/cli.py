"""CLI for reference validation of generated ETL semantic suites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.paths import (
    default_etl_test_dir,
    default_generated_tests_root,
    default_references_root,
    default_results_root,
)
from etl.reference_validation.models import ReferenceValidationContext
from etl.reference_validation.results import write_results
from etl.reference_validation.runner import validate_suite
from etl.reference_validation.technical_status import filter_technically_valid_suites
from etl.suites.discovery import discover_suites


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
        "--references-root",
        type=Path,
        default=default_references_root(),
        help="Root containing reference <task>.etl files.",
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=default_results_root(),
        help="Root where per-task reference-validation CSV files are written.",
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
        "--include-unchecked",
        action="store_true",
        help=(
            "Validate suites even when generated_suite_technical_validation.csv "
            "does not mark them technically_valid=True."
        ),
    )
    parser.add_argument(
        "--no-promote",
        action="store_true",
        help="Do not copy passing suites into <task>/validated/<llm>/<strategy>/<suite_id>.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and filter suites, but do not inject files or run Maven.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    suites = discover_suites(args)
    if not suites:
        task = args.task or "*"
        print(f"No candidate suites found for task {task}", file=sys.stderr)
        return 1

    suites = filter_technically_valid_suites(suites, args)
    if not suites:
        print(
            "No technically valid candidate suites to reference-validate. "
            "Use --include-unchecked to override.",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        for suite in suites:
            print(f"Would validate {suite.path}")
        return 0

    context = ReferenceValidationContext(
        etl_test_dir=args.etl_test_dir.resolve(),
        references_root=args.references_root.resolve(),
        results_root=args.results_root.resolve(),
        timeout=args.timeout,
        promote=not args.no_promote,
    )

    rows: list[dict[str, str]] = []
    for suite in suites:
        print(f"Validating {suite.task} | {suite.llm} | {suite.strategy} | {suite.suite_id}")
        result = validate_suite(suite, context)
        rows.append(result.as_row())
        print(
            "  valid="
            f"{result.valid} compiles={result.compiles} "
            f"executes={result.executes} reference_pass={result.reference_pass} "
            f"status={result.status}"
        )
        if result.error_summary:
            print(f"  error: {result.error_summary}")

    write_results(rows, args)
    failed = sum(1 for row in rows if row["valid"] != "True")
    return 0 if failed == 0 else 1
