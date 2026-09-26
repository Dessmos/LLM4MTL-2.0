"""Copy a generated suite's Java sources and model files into a harness workspace."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.external_tools.maven import MAVEN_TEST_RESOURCES_DIR
from llm4mtl.workspace.injection import Injection
from llm4mtl.semantic_tests.semantic_spec import MODELS_DIRECTORY
from llm4mtl.semantic_tests.suites.generated_models import generated_models_dir
from llm4mtl.semantic_tests.suites.java import infer_fqcn, java_destination
from llm4mtl.domain import GeneratedSuite


def inject_suite(
    suite: GeneratedSuite,
    java_paths: list[Path],
    model_paths: list[Path],
    test_project_dir: Path,
    injection: Injection,
) -> None:
    for java_path in java_paths:
        fqcn = infer_fqcn(java_path)
        injection.copy_file(java_path, java_destination(test_project_dir, fqcn))

    task_resource_dir = (
        test_project_dir / MAVEN_TEST_RESOURCES_DIR / generated_models_dir(suite.task)
    )
    for model_path in model_paths:
        relative = model_path.relative_to(suite.path / MODELS_DIRECTORY)
        injection.copy_file(model_path, task_resource_dir / relative)
