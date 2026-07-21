#!/usr/bin/env python3
"""Validate selected generated ETL transformations with the Epsilon parser."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from run_parser import check_etl_syntax


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRANSFORMATIONS_ROOT = (
    REPO_ROOT / "Workflows" / "n8n-docker" / "mtl_snippets" / "ETL_language" / "responses"
)
DEFAULT_RESULTS_FILE = Path(__file__).resolve().parent / "results" / "etl" / "generated_transformation_syntax.csv"
RESULT_COLUMNS = ["language", "task", "model", "strategy", "path", "parsed", "problem_count"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check syntax of selected generated ETL transformations.")
    parser.add_argument("--transformation", action="append", type=Path, help="Specific .etl file; repeatable.")
    parser.add_argument("--transformations-root", type=Path, default=DEFAULT_TRANSFORMATIONS_ROOT)
    parser.add_argument("--task", action="append", help="Task name; repeatable.")
    parser.add_argument("--model", action="append", help="Transformation model; repeatable.")
    parser.add_argument("--strategy", action="append", help="Transformation strategy; repeatable.")
    parser.add_argument("--results-file", type=Path, default=DEFAULT_RESULTS_FILE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser.parse_args(argv)


def discover_transformations(args: argparse.Namespace) -> list[dict[str, object]]:
    root = args.transformations_root.resolve()
    paths = [path.resolve() for path in args.transformation] if args.transformation else sorted(root.glob("*/*/*.etl"))
    selected: list[dict[str, object]] = []
    for path in paths:
        if not path.is_file() or path.suffix.lower() != ".etl":
            continue
        try:
            relative = path.relative_to(root)
            model, strategy = relative.parts[:2]
        except (ValueError, IndexError):
            model = path.parent.parent.name
            strategy = path.parent.name
        task = path.stem
        if args.task and task not in args.task:
            continue
        if args.model and model not in args.model:
            continue
        if args.strategy and strategy not in args.strategy:
            continue
        selected.append({"path": path, "task": task, "model": model, "strategy": strategy})
    return selected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    selected = discover_transformations(args)
    if not selected:
        return emit(args, {"status": "error", "error": "No generated ETL transformations matched.", "selected": 0}, 1)

    if args.dry_run:
        payload = {
            "status": "dry_run",
            "selected": len(selected),
            "transformations": [str(item["path"]) for item in selected],
        }
        return emit(args, payload, 0)

    rows: list[dict[str, str]] = []
    for item in selected:
        parsed, problem_count = check_etl_syntax(str(item["path"]))
        rows.append(
            {
                "language": "etl",
                "task": str(item["task"]),
                "model": str(item["model"]),
                "strategy": str(item["strategy"]),
                "path": str(item["path"]),
                "parsed": str(parsed),
                "problem_count": str(problem_count),
            }
        )

    args.results_file.parent.mkdir(parents=True, exist_ok=True)
    with args.results_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(row["parsed"] == "True" for row in rows)
    payload = {
        "status": "completed",
        "selected": len(rows),
        "passed": passed,
        "failed": len(rows) - passed,
        "passed_transformations": [row["path"] for row in rows if row["parsed"] == "True"],
        "failed_transformations": [row["path"] for row in rows if row["parsed"] != "True"],
        "results_file": str(args.results_file.resolve()),
    }
    return emit(args, payload, 0 if passed == len(rows) else 1)


def emit(args: argparse.Namespace, payload: dict[str, object], exit_code: int) -> int:
    if args.output_format == "json":
        print(json.dumps(payload, ensure_ascii=False))
    elif payload.get("status") == "dry_run":
        print(f"Selected transformations: {payload['selected']}")
        for path in payload["transformations"]:
            print(path)
    elif payload.get("status") == "completed":
        print(
            f"Syntax validation: selected={payload['selected']} "
            f"passed={payload['passed']} failed={payload['failed']}"
        )
        print(f"Results: {payload['results_file']}")
    else:
        print(str(payload.get("error", "Unknown error")), file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
