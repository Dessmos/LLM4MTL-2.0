"""CLI to build deterministic test-generation prompts from task contracts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common.paths import (
    default_prompts_root,
    default_references_root,
    default_task_contracts_root,
)
from etl.contracts import load_task_contract
from etl.prompt_generation.builder import build_test_generation_prompt


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble deterministic ETL test-generation prompts from reference "
            "transformations and their task contracts. The factual parts of each "
            "prompt come from the contract; only the LLM's answer is free."
        )
    )
    parser.add_argument(
        "--task",
        help="Only build the prompt for this task, e.g. lazy. Defaults to all references.",
    )
    parser.add_argument(
        "--llm",
        default="gpt-5",
        help="LLM subfolder under the prompts root to write into.",
    )
    parser.add_argument(
        "--references-root",
        type=Path,
        default=default_references_root(),
        help="Directory containing reference <task>.etl files.",
    )
    parser.add_argument(
        "--contracts-root",
        type=Path,
        default=default_task_contracts_root(),
        help="Directory containing <task>.json contracts.",
    )
    parser.add_argument(
        "--prompts-root",
        type=Path,
        default=default_prompts_root(),
        help="Root under which <llm>/<task>.txt prompts are written.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be written without creating files.",
    )
    return parser.parse_args(argv)


def reference_paths(args: argparse.Namespace) -> list[Path]:
    if args.task:
        return [args.references_root / f"{args.task}.etl"]
    return sorted(args.references_root.glob("*.etl"))


def build_one(reference_path: Path, args: argparse.Namespace) -> tuple[bool, str]:
    task = reference_path.stem
    if not reference_path.exists():
        return False, f"reference transformation not found: {reference_path}"

    contract = load_task_contract(task, contracts_root=args.contracts_root)
    if contract is None:
        return False, (
            f"no contract for task '{task}' under {args.contracts_root}. "
            "Run build_task_model_contracts.py first."
        )

    prompt = build_test_generation_prompt(contract, reference_path.read_text(encoding="utf-8"))
    output_path = args.prompts_root / args.llm / f"{task}.txt"
    if args.dry_run:
        return True, f"would write {output_path}"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(prompt, encoding="utf-8")
    return True, f"wrote {output_path}"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    references = reference_paths(args)
    if not references:
        print(f"No reference transformations found under {args.references_root}", file=sys.stderr)
        return 1

    ok_count = 0
    fail_count = 0
    for reference_path in references:
        ok, message = build_one(reference_path, args)
        if ok:
            ok_count += 1
            print(f"OK: {message}")
        else:
            fail_count += 1
            print(f"ERROR: {message}", file=sys.stderr)

    print(f"Built prompts: {ok_count}; failed: {fail_count}")
    return 0 if fail_count == 0 else 1
