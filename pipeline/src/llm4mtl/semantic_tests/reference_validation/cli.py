"""CLI for reference validation of generated ETL semantic suites."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm4mtl.domain import GeneratedSuite
from llm4mtl.languages import language_adapter
from llm4mtl.run_store.models import WORKSPACES_DIRNAME
from llm4mtl.semantic_tests.reference_validation.results import write_results
from llm4mtl.semantic_tests.reference_validation.runner import reference_row, validate_suite
from llm4mtl.semantic_tests.suites.cli_options import (
    add_suite_run_arguments,
    add_suite_selection_arguments,
)
from llm4mtl.semantic_tests.suites.discovery import SuiteIdentityError, discover_suites
from llm4mtl.semantic_tests.suites.java import JavaSourceError
from llm4mtl.semantic_tests.validation import REFERENCE_INVALID, ValidationContext, workspace_for
from llm4mtl.workspace import materialize_engine

# This command validates ETL suites only.
LANGUAGE = "etl"

# The default Maven timeout, used only when no technical-validation
# observation exists yet for a suite. Otherwise that recorded run is reused.
REFERENCE_VALIDATION_TIMEOUT_SECONDS = 240


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generated ETL semantic suites against reference transformations."
    )
    add_suite_selection_arguments(parser, verb="validate")
    add_suite_run_arguments(
        parser,
        results_name="reference-validation",
        timeout_seconds=REFERENCE_VALIDATION_TIMEOUT_SECONDS,
    )
    _add_stage_arguments(parser)
    return parser.parse_args(argv)


def _add_stage_arguments(parser: argparse.ArgumentParser) -> None:
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
        "--dry-run",
        action="store_true",
        help="Discover suites, but do not inject files or run Maven.",
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
