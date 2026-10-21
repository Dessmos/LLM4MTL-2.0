"""Where a transformation is copied inside the ETL harness project."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.external_tools.maven import MAVEN_TEST_RESOURCES_DIR


def transformation_destination(etl_test_dir: Path, task: str) -> Path:
    return etl_test_dir / MAVEN_TEST_RESOURCES_DIR / "transformations" / f"{task}.etl"
