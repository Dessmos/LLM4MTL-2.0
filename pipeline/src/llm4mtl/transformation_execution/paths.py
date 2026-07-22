"""Repository paths owned or consumed by transformation validation."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # v5 migration: this package now lives under pipeline/llm4mtl/, but the
    # Transformation_Validation output dirs, Test_Generation suites, Workflows and
    # ETL_Test it references still live in the nested project folder.
    from llm4mtl.paths import LEGACY_PROJECT_ROOT

    return LEGACY_PROJECT_ROOT


def validation_root() -> Path:
    # v5 final cleanup: transformation-validation output lives under artifacts/work/.
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "transformation_validation"


def default_validated_tests_root() -> Path:
    # v5 final cleanup: generated test suites live under artifacts/work/test_generation.
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "test_generation" / "generated_tests" / "etl"


def default_transformations_root() -> Path:
    # v5 migration (Stage 3): the transformation-generation n8n tree moved to
    # workflows/n8n/transformations.
    from llm4mtl.paths import TARGET

    return (
        TARGET.workflows
        / "transformations"
        / "mtl_snippets"
        / "ETL_language"
        / "responses"
    )


def default_etl_test_dir() -> Path:
    # v5 migration (Stage 2): the ETL test-harness engine moved to engines/etl/harness.
    from llm4mtl.paths import TARGET

    return TARGET.engine_harness("etl")


def default_artifacts_root() -> Path:
    return validation_root() / "artifacts" / "etl"


def default_results_root() -> Path:
    return validation_root() / "results" / "etl"


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path.resolve())
