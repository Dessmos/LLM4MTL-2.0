"""Reference transformation injection helpers."""

from __future__ import annotations

from pathlib import Path


def transformation_destination(etl_test_dir: Path, task: str) -> Path:
    return (
        etl_test_dir / "src" / "test" / "resources" / "transformations" / f"{task}.etl"
    )
