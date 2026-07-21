"""Write the persistent CSV index for validation runs."""

from __future__ import annotations

import csv
from pathlib import Path

from common.csv_utils import write_rows
from transformation_validation.models import RESULT_COLUMNS, TransformationValidationResult


READABLE_REPORT_COLUMNS = ["Field", "Value"]


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
        task_root = results_root.resolve() / task
        index_path = task_root / "generated_transformation_validation.csv"
        write_rows(index_path, rows, RESULT_COLUMNS, append=append)
        paths.append(index_path)

        readable_path = task_root / "generated_transformation_validation_report.csv"
        write_readable_report(
            readable_path,
            [result for result in results if result.pair.suite.task == task],
            append=append,
        )
        paths.append(readable_path)
    return paths


def write_readable_report(
    path: Path,
    results: list[TransformationValidationResult],
    append: bool,
) -> None:
    """Write a two-column report intended for direct reading in a spreadsheet."""

    path.parent.mkdir(parents=True, exist_ok=True)
    append_to_existing = append and path.exists()
    with path.open("a" if append_to_existing else "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        if not append_to_existing:
            writer.writerow(READABLE_REPORT_COLUMNS)
        for result in results:
            writer.writerow((evaluation_heading(result), ""))
            writer.writerows(readable_rows(result))
            writer.writerow(("--- End of evaluation ---", ""))
            writer.writerow([])


def readable_rows(result: TransformationValidationResult) -> list[tuple[str, str]]:
    """Create labelled rows for one suite/transformation evaluation."""

    pair = result.pair
    return [
        ("Task", pair.suite.task),
        (
            "Transformation",
            f"{pair.transformation.llm} / {pair.transformation.strategy} / {pair.transformation.path.name}",
        ),
        ("Test suite", f"{pair.suite.llm} / {pair.suite.strategy} / {pair.suite.suite_id}"),
        ("Test result", "PASS" if result.tests_pass else "FAIL"),
        ("Compilation", "PASS" if result.compiles else "FAIL"),
        ("Test execution", "PASS" if result.executes else "FAIL"),
        ("Failure stage", result.failure_stage or "Not applicable"),
        ("Explanation", result.error_summary or "All tests passed."),
        ("Artifacts", result.artifact_dir),
        ("Run ID", result.run_id),
    ]


def evaluation_heading(result: TransformationValidationResult) -> str:
    pair = result.pair
    return (
        f"=== Task: {pair.suite.task} | "
        f"Transformation: {pair.transformation.llm}/{pair.transformation.strategy} | "
        f"Suite: {pair.suite.llm}/{pair.suite.strategy}/{pair.suite.suite_id} ==="
    )
