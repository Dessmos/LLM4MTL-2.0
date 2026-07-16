"""Repository paths owned or consumed by transformation validation."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def validation_root() -> Path:
    return repo_root() / "Transformation_Validation"


def default_validated_tests_root() -> Path:
    return repo_root() / "Test_Generation" / "generated_tests" / "etl"


def default_transformations_root() -> Path:
    return repo_root() / "ETL_Parser" / "src" / "main" / "resources"


def default_etl_test_dir() -> Path:
    return repo_root() / "ETL_Test"


def default_artifacts_root() -> Path:
    return validation_root() / "artifacts" / "etl"


def default_results_root() -> Path:
    return validation_root() / "results" / "etl"


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path.resolve())
