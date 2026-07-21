"""Generated suite injection helpers shared by validation stages."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.workspace.injection import Injection
from llm4mtl.semantic_tests.suites.java import infer_fqcn, java_destination, slug
from llm4mtl.semantic_tests.suites.models import CandidateSuite


def inject_suite(
    suite: CandidateSuite,
    java_paths: list[Path],
    model_paths: list[Path],
    test_project_dir: Path,
    injection: Injection,
) -> None:
    for java_path in java_paths:
        fqcn = infer_fqcn(java_path)
        injection.copy_file(java_path, java_destination(test_project_dir, fqcn))

    task_resource_dir = (
        test_project_dir
        / "src"
        / "test"
        / "resources"
        / "generated-models"
        / slug(suite.task)
    )
    for model_path in model_paths:
        relative = model_path.relative_to(suite.path / "models")
        injection.copy_file(model_path, task_resource_dir / relative)


def suite_model_paths(suite_path: Path) -> list[Path]:
    models_dir = suite_path / "models"
    if not models_dir.exists():
        return []
    return sorted(path for path in models_dir.rglob("*") if path.is_file())
