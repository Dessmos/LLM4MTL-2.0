"""Result CSV writing for reference validation."""

from __future__ import annotations

import argparse

from llm4mtl.serialization.csv_exports import write_rows
from llm4mtl.semantic_tests.reference_validation.models import RESULT_COLUMNS


def write_results(rows: list[dict[str, str]], args: argparse.Namespace) -> None:
    by_task: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_task.setdefault(row["task"], []).append(row)

    for task, task_rows in sorted(by_task.items()):
        out_path = args.results_root.resolve() / task / "generated_suite_validation.csv"
        write_rows(out_path, task_rows, RESULT_COLUMNS, append=args.append)
        print(f"Wrote {out_path}")
