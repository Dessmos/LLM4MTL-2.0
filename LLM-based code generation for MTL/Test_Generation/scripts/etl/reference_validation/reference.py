"""Reference transformation injection helpers."""

from __future__ import annotations

from pathlib import Path

from common.injection import Injection


def reference_transformation_path(references_root: Path, task: str) -> Path:
    return references_root / f"{task}.etl"


def transformation_destination(etl_test_dir: Path, task: str) -> Path:
    return etl_test_dir / "src" / "test" / "resources" / "transformations" / f"{task}.etl"


def inject_reference_transformation(
    task: str,
    etl_test_dir: Path,
    references_root: Path,
    injection: Injection,
) -> tuple[bool, str]:
    reference_path = reference_transformation_path(references_root, task)
    if not reference_path.exists():
        return False, f"Reference transformation not found: {reference_path}"

    injection.copy_file(reference_path, transformation_destination(etl_test_dir, task))
    return True, ""
