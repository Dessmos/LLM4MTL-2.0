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
    from llm4mtl.paths import REPO_ROOT

    return REPO_ROOT


def test_generation_root() -> Path:
    # v5 final cleanup: generated test suites and their metrics are OUTPUT; they now
    # live under artifacts/work/ (the old nested Test_Generation dir is retired).
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "test_generation"


def _n8n_tests_root() -> Path:
    # v5 migration (Stage 3): the test-generation n8n tree moved to workflows/n8n/tests.
    from llm4mtl.paths import TARGET

    return TARGET.workflows / "tests"


def n8n_snippets_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return (
        _n8n_tests_root()
        / "mtl_snippets"
        / config.snippets_dir
    )


def n8n_workflows_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return (
        _n8n_tests_root()
        / "workflows"
        / f"{config.language_key}_variants"
    )


def default_responses_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return n8n_snippets_root(config) / "responses"


def default_generated_tests_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return test_generation_root() / "generated_tests" / config.generated_tests_dir


def default_prompts_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return n8n_snippets_root(config) / "prompts"


def _benchmark_tasks_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    # v5 migration (Stage 3): hand-authored task inputs (references, task contracts)
    # moved out of the n8n tree into benchmark/tasks/<lang>/.
    from llm4mtl.paths import TARGET

    return TARGET.benchmark / "tasks" / config.language_key


def default_task_contracts_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return _benchmark_tasks_root(config) / "task_contracts"


def default_references_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return _benchmark_tasks_root(config) / "references"


def default_test_project_dir(config: LanguageConfig = ETL_CONFIG) -> Path:
    # v5 migration (Stage 2): the test-harness engine moved to engines/<lang>/harness.
    from llm4mtl.paths import TARGET

    return TARGET.engine_harness(config.language_key)


def default_etl_test_dir() -> Path:
    return default_test_project_dir(ETL_CONFIG)


def default_results_root(config: LanguageConfig = ETL_CONFIG) -> Path:
    return test_generation_root() / "results" / config.generated_tests_dir


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path.resolve())
