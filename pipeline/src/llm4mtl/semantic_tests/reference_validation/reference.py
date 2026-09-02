"""Reference transformation injection helpers."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.workspace.injection import Injection


def reference_transformation_path(references_root: Path, task: str) -> Path:
    return references_root / f"{task}.etl"


def transformation_destination(etl_test_dir: Path, task: str) -> Path:
    return (
        etl_test_dir / "src" / "test" / "resources" / "transformations" / f"{task}.etl"
    )
