"""CLI for extracting generated ETL suites from Markdown responses."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm4mtl.conventions import default_generated_tests_root, default_responses_root
from llm4mtl.semantic_tests.extraction.discovery import discover_responses
from llm4mtl.semantic_tests.extraction.models import ResponseTarget
from llm4mtl.semantic_tests.extraction.parser import extract_files, java_files, semantic_case_files
from llm4mtl.semantic_tests.extraction.semantic_cases import can_generate_java_from_semantic_cases
from llm4mtl.semantic_tests.extraction.writer import write_suite


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract generated ETL semantic test suites from Markdown responses."
    )
    parser.add_argument(
        "--response",
        action="append",
        type=Path,
        help=(
            "Specific Markdown response file to extract. Can be repeated. "
            "If omitted, scans responses root."
        ),
    )
    parser.add_argument(
        "--responses-root",
        type=Path,
        default=default_responses_root(),
        help="Root containing <llm>/<strategy>/<task>.md responses.",
    )
    parser.add_argument(
        "--generated-tests-root",
        type=Path,
        default=default_generated_tests_root(),
        help="Root where <task>/candidates suites are written.",
    )
    parser.add_argument(
        "--task",
        help=(
            "Only extract this task, e.g. Tree2Graph. If omitted, extracts all "
            "*.md responses found under responses root."
        ),
    )
    parser.add_argument(
        "--llm",
        help="Override LLM name when --response is outside the standard tree.",
    )
    parser.add_argument(
        "--strategy",
        help="Override strategy name when --response is outside the standard tree.",
    )
    parser.add_argument(
        "--suite-id",
        help="Explicit suite id, e.g. suite_001. Allowed only with one response.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the target suite directory if it already exists.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write extracted files even if no Java file or semantic_cases.json is found.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report what would be written without creating files.",
    )
    return parser.parse_args(argv)


def extract_one(target: ResponseTarget, args: argparse.Namespace) -> tuple[bool, str]:
    if not target.response_path.exists():
        return False, f"response not found: {target.response_path}"

    markdown = target.response_path.read_text(encoding="utf-8")
    extracted = extract_files(markdown)
    has_java = bool(java_files(extracted))
    has_semantic_cases = bool(semantic_case_files(extracted))
    has_supported_semantic_cases = has_semantic_cases and can_generate_java_from_semantic_cases(target.task)
    if not has_java and not has_supported_semantic_cases and not args.allow_incomplete:
        if has_semantic_cases:
            return False, f"semantic_cases.json is not supported for {target.task} yet: {target.response_path}"
        return False, f"no Java file block or supported semantic_cases.json block found in {target.response_path}"

    suite_dir, enforcement = write_suite(target, extracted, args)
    action = "would write" if args.dry_run else "wrote"
    if not enforcement.valid:
        reason = "; ".join(enforcement.violations)
        return True, f"{action} {suite_dir} [INVALID: contract violation] {reason}"
    return True, f"{action} {suite_dir}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets = discover_responses(args)
    if not targets:
        task = f"{args.task}.md" if args.task else "*.md"
        print(f"No {task} responses found under {args.responses_root}", file=sys.stderr)
        return 1

    ok_count = 0
    fail_count = 0
    for target in targets:
        ok, message = extract_one(target, args)
        if ok:
            ok_count += 1
            print(f"OK: {message}")
        else:
            fail_count += 1
            print(f"ERROR: {message}", file=sys.stderr)

    print(f"Extracted: {ok_count}; failed: {fail_count}")
    return 0 if fail_count == 0 else 1
