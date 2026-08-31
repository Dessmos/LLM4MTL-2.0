"""Repository paths owned or consumed by transformation validation."""

from __future__ import annotations

from pathlib import Path


def validation_root() -> Path:
    # v5 final cleanup: transformation-validation output lives under artifacts/work/.
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "transformation_validation"


def default_validated_tests_root() -> Path:
    # v5 final cleanup: generated test suites live under artifacts/work/test_generation.
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "test_generation" / "generated_tests" / "etl"


def default_transformations_root() -> Path:
    # Generated transformation responses are runtime artifacts, not workflow
    # definitions or immutable prompt assets.
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "transformation_generation" / "etl" / "responses"


def default_test_project_dir() -> Path:
    """The ETL harness. One owner: the shared per-language convention."""
    from llm4mtl.conventions import ETL_CONFIG, default_test_project_dir as engine_harness

    return engine_harness(ETL_CONFIG)


def default_artifacts_root() -> Path:
    return validation_root() / "artifacts" / "etl"


def default_results_root() -> Path:
    return validation_root() / "results" / "etl"
