"""Shared repository paths for the generated-test workflow."""

from __future__ import annotations

from pathlib import Path


LANGUAGE_ETL = "ETL"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_generation_root() -> Path:
    return repo_root() / "Test_Generation"


def n8n_snippets_root() -> Path:
    return (
        test_generation_root()
        / "Workflows"
        / "n8n-docker"
        / "mtl_snippets"
        / "ETL_test_generation"
    )


def default_responses_root() -> Path:
    return n8n_snippets_root() / "responses"


def default_generated_tests_root() -> Path:
    return test_generation_root() / "generated_tests" / "etl"


def default_prompts_root() -> Path:
    return n8n_snippets_root() / "prompts"


def default_references_root() -> Path:
    return n8n_snippets_root() / "references"


def default_etl_test_dir() -> Path:
    return repo_root() / "ETL_Test"


def default_results_root() -> Path:
    return test_generation_root() / "results" / "etl"


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path.resolve())
