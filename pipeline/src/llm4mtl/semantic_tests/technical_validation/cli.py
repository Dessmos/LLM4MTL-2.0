"""CLI for technical validation of extracted generated ETL suites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm4mtl.domain import GeneratedSuite
from llm4mtl.languages import language_adapter
from llm4mtl.run_store.models import WORKSPACES_DIRNAME
from llm4mtl.semantic_tests.suites.cli_options import (
    add_suite_run_arguments,
    add_suite_selection_arguments,
)
from llm4mtl.semantic_tests.suites.discovery import SuiteIdentityError, discover_suites
from llm4mtl.semantic_tests.suites.java import JavaSourceError
from llm4mtl.semantic_tests.technical_validation.results import write_results
from llm4mtl.semantic_tests.technical_validation.suite import check_suite, technical_row
from llm4mtl.semantic_tests.validation import ValidationContext, workspace_for
from llm4mtl.workspace import materialize_engine

# This command validates ETL suites only.
LANGUAGE = "etl"

# The default Maven timeout. Reference validation reuses the observation this
# stage records, so the execution it reuses ran under this timeout.
TECHNICAL_VALIDATION_TIMEOUT_SECONDS = 180


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check technical validity of extracted generated ETL test suites."
    )
    add_suite_selection_arguments(parser, verb="check")
    add_suite_run_arguments(
        parser,
        results_name="technical validation",
        timeout_seconds=TECHNICAL_VALIDATION_TIMEOUT_SECONDS,
    )
    _add_stage_arguments(parser)
    return parser.parse_args(argv)


def _add_stage_arguments(parser: argparse.ArgumentParser) -> None:
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
        "--dry-run",
        action="store_true",
        help="Discover suites and print what would be checked.",
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return _run(args)
    except (SuiteIdentityError, JavaSourceError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    suites = discover_suites(args, LANGUAGE)
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
        args.observations_root.resolve().parent / WORKSPACES_DIRNAME,
        LANGUAGE,
    )
    context = ValidationContext(
        adapter=language_adapter(LANGUAGE),
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
