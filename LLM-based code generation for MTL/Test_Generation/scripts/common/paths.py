"""Shared repository paths for the generated-test workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LANGUAGE_ETL = "ETL"


@dataclass(frozen=True)
class LanguageConfig:
    """Filesystem conventions for one generated-test language workflow."""

    language: str
    generated_tests_dir: str
    snippets_dir: str
    test_project_dir: str

    @property
    def language_key(self) -> str:
        return self.language.lower()


ETL_CONFIG = LanguageConfig(
    language=LANGUAGE_ETL,
    generated_tests_dir="etl",
    snippets_dir="ETL_test_generation",
    test_project_dir="ETL_Test",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_generation_root() -> Path:
    return repo_root() / "Test_Generation"


def n8n_snippets_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return (
        test_generation_root()
        / "Workflows"
        / "n8n-docker"
        / "mtl_snippets"
        / config.snippets_dir
    )


def n8n_workflows_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return (
        test_generation_root()
        / "Workflows"
        / "n8n-docker"
        / "workflows"
        / f"{config.language_key}_variants"
    )


def default_responses_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return n8n_snippets_root(config) / "responses"


def default_generated_tests_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return test_generation_root() / "generated_tests" / config.generated_tests_dir


def default_prompts_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return n8n_snippets_root(config) / "prompts"


def default_references_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return n8n_snippets_root(config) / "references"


def default_test_project_dir(config: LanguageConfig = ETL_CONFIG) -> Path:
    return repo_root() / config.test_project_dir


def default_etl_test_dir() -> Path:
    return default_test_project_dir(ETL_CONFIG)


def default_results_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return test_generation_root() / "results" / config.generated_tests_dir


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path.resolve())
