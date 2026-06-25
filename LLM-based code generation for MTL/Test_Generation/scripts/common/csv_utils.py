"""CSV helpers for the generated-test workflow."""

from __future__ import annotations

import csv
from pathlib import Path


def write_rows(path: Path, rows: list[dict[str, str]], columns: list[str], append: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    append_to_existing = append and path.exists()
    with path.open("a" if append_to_existing else "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if not append_to_existing:
            writer.writeheader()
        writer.writerows(rows)
