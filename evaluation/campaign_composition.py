"""Describe what the evaluation campaign consists of: tasks and configurations."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import EvaluationInputError, read_json_object, read_run_manifest, write_csv
from evaluation.rq_metrics import DEFAULT_SELECTION_ROOT, discover_groups
from llm4mtl.paths import TARGET


MIXED = "mixed"
ALL = "ALL"
TASK_FIELDS = ("language", "tasks", "share")
CONFIGURATION_FIELDS = ("configuration", "groups", "runs", "group_names")


@dataclass(frozen=True)
class GroupComposition:
    """One evaluation group: its configuration and the tasks its runs cover."""

    name: str
    configuration: str
    tasks: frozenset[tuple[str, str]]
    runs: int


def configuration_label(llms: Mapping[str, Mapping[str, Any]]) -> str:
    """The one model that fills every LLM role, else ``mixed``."""
    models = {str(role["model"]) for role in llms.values()}
    if not models:
        raise EvaluationInputError("batch configuration names no LLM roles")
    return models.pop() if len(models) == 1 else MIXED


def task_rows(groups: Sequence[GroupComposition]) -> list[dict[str, Any]]:
    """Tasks per language over the task set that every group covers."""
    task_sets = {group.tasks for group in groups}
    if len(task_sets) != 1:
        raise EvaluationInputError("evaluation groups do not cover the same benchmark tasks")
    per_language = Counter(language for language, _ in task_sets.pop())
    total = sum(per_language.values())
    rows = [
        {"language": language, "tasks": count, "share": round(count / total, 6)}
        for language, count in sorted(per_language.items())
    ]
    rows.append({"language": ALL, "tasks": total, "share": 1.0})
    return rows


def configuration_rows(groups: Sequence[GroupComposition]) -> list[dict[str, Any]]:
    """Evaluation groups and runs per configuration, then the campaign total."""
    rows = []
    for configuration in sorted({group.configuration for group in groups}):
        members = [group for group in groups if group.configuration == configuration]
        rows.append(
            {
                "configuration": configuration,
                "groups": len(members),
                "runs": sum(group.runs for group in members),
                "group_names": ";".join(group.name for group in members),
            }
        )
    rows.append(
        {"configuration": ALL, "groups": len(groups), "runs": sum(group.runs for group in groups), "group_names": ""}
    )
    return rows


def read_compositions(selection_root: Path) -> tuple[GroupComposition, ...]:
    """Read the configuration and task set of every selected group."""
    compositions = []
    for group in discover_groups(selection_root):
        tasks = set()
        for batch_id, run_id in group.runs:
            manifest = read_run_manifest(TARGET.run_dir(batch_id, run_id))
            tasks.add((str(manifest["language"]), str(manifest["task"])))
        labels = {
            configuration_label(read_json_object(TARGET.batch_dir(batch_id) / "batch.json")["config"]["llms"])
            for batch_id in sorted({batch_id for batch_id, _ in group.runs})
        }
        if len(labels) != 1:
            raise EvaluationInputError(f"group {group.name} mixes configurations: {sorted(labels)}")
        compositions.append(GroupComposition(group.name, labels.pop(), frozenset(tasks), len(group.runs)))
    return tuple(compositions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--selection-root", type=Path, default=DEFAULT_SELECTION_ROOT,
                        help="tree of evaluation groups (default: artifacts/Chosen_for_evaluation)")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for the two CSV files")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        groups = read_compositions(args.selection_root)
        tables = {
            "campaign-tasks.csv": (TASK_FIELDS, task_rows(groups)),
            "campaign-configurations.csv": (CONFIGURATION_FIELDS, configuration_rows(groups)),
        }
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for name, (fields, rows) in tables.items():
        write_csv(args.output_dir / name, fields, rows)
        print(args.output_dir / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
