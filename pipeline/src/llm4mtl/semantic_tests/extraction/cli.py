"""CLI for extracting generated semantic-test suites from Markdown responses.

The language is a required argument, not a default. It used to be hardcoded to
ETL here while the roots came from ETL conventions, so pointing this command at
an ATL, QVT-O, or Reactions response silently rendered an ETL harness and wrote
it into the ETL tree.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm4mtl.conventions import (
    default_generated_tests_root,
    default_responses_root,
    language_config,
)
from llm4mtl.languages import REQUIRED_LANGUAGES, language_adapter
from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.semantic_tests.extraction.discovery import discover_responses
from llm4mtl.semantic_tests.extraction.models import ResponseTarget
from llm4mtl.semantic_tests.extraction.parser import extract_files
from llm4mtl.semantic_tests.extraction.writer import write_suite


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract generated semantic test suites from Markdown responses "
            "for one language."
        )
    )
    parser.add_argument(
        "--language",
        choices=sorted(REQUIRED_LANGUAGES),
        required=True,
        help="Language whose adapter renders the harness and whose roots are used.",
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
        help=(
            "Root containing <llm>/<strategy>/<task>.md responses. "
            "Defaults to the selected language's responses root."
        ),
    )
    parser.add_argument(
        "--generated-tests-root",
        type=Path,
        help=(
            "Root where <task>/candidates suites are written. "
            "Defaults to the selected language's generated-tests root."
        ),
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
        help=(
            "Deprecated compatibility flag. Existing candidate suites are immutable; "
            "choose a new --suite-id instead."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report what would be written without creating files.",
    )
    args = parser.parse_args(argv)
    config = language_config(args.language)
    if args.responses_root is None:
        args.responses_root = default_responses_root(config)
    if args.generated_tests_root is None:
        args.generated_tests_root = default_generated_tests_root(config)
    return args


def extract_one(
    target: ResponseTarget,
    args: argparse.Namespace,
    adapter: LanguageAdapter,
) -> tuple[bool, str]:
    """Extract one response. Returns whether it yielded a usable suite, and why not.

    An artifact-invalid suite is still written: it is the evidence behind the
    funnel's artifact-valid rate, and dropping it would quietly shrink that
    denominator. It is reported as a failure because the response did not
    produce a usable semantic-test specification.
    """
    if not target.response_path.exists():
        return False, f"response not found: {target.response_path}"

    markdown = target.response_path.read_text(encoding="utf-8")
    extracted = extract_files(markdown)
    if not extracted:
        return False, f"no extractable artifact blocks found in {target.response_path}"

    suite_dir, validation = write_suite(target, extracted, args, adapter)
    action = "would write" if args.dry_run else "wrote"
    if not validation.valid:
        reason = "; ".join(validation.violations)
        return False, f"{action} {suite_dir} [INVALID: {validation.reason_code}] {reason}"
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
    adapter = language_adapter(args.language)
    for target in targets:
        ok, message = extract_one(target, args, adapter)
        if ok:
            ok_count += 1
            print(f"OK: {message}")
        else:
            fail_count += 1
            print(f"ERROR: {message}", file=sys.stderr)

    print(f"Extracted: {ok_count}; failed: {fail_count}")
    return 0 if fail_count == 0 else 1
