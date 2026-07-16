"""Write the persistent CSV index for validation runs."""

from __future__ import annotations

from pathlib import Path

from common.csv_utils import write_rows
from transformation_validation.models import RESULT_COLUMNS, TransformationValidationResult


def write_results(
    results: list[TransformationValidationResult],
    results_root: Path,
    append: bool = True,
) -> list[Path]:
    by_task: dict[str, list[dict[str, str]]] = {}
    for result in results:
        by_task.setdefault(result.pair.suite.task, []).append(result.as_row())

    paths: list[Path] = []
    for task, rows in sorted(by_task.items()):
        path = results_root.resolve() / task / "generated_transformation_validation.csv"
        write_rows(path, rows, RESULT_COLUMNS, append=append)
        paths.append(path)
    return paths
