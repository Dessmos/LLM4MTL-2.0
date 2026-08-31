"""Filesystem conventions of the generated-test workflow, per language.

Every helper here takes the language explicitly. They used to default to ETL,
which meant an ATL or Reactions caller silently received ETL paths and produced
results attributed to a language that never ran. Requiring the argument turns
every remaining ETL assumption into something visible at the call site, and an
unimplemented language into a loud failure at :func:`language_config`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LANGUAGE_ETL = "ETL"
LANGUAGE_ATL = "ATL"
LANGUAGE_QVTO = "QVTO"
LANGUAGE_REACTIONS = "REACTIONS"


@dataclass(frozen=True)
class LanguageConfig:
    """Filesystem conventions for one generated-test language workflow."""

    language: str
    workflow_language: str
    generated_tests_dir: str
    snippets_dir: str
    test_project_dir: str

    @property
    def language_key(self) -> str:
        return self.language.lower()


ETL_CONFIG = LanguageConfig(
    language=LANGUAGE_ETL,
    workflow_language="ETL",
    generated_tests_dir="etl",
    snippets_dir="ETL_test_generation",
    test_project_dir="ETL_Test",
)

ATL_CONFIG = LanguageConfig(
    language=LANGUAGE_ATL,
    workflow_language="ATL",
    generated_tests_dir="atl",
    snippets_dir="ATL_test_generation",
    test_project_dir="ATL_Tests",
)

QVTO_CONFIG = LanguageConfig(
    language=LANGUAGE_QVTO,
    workflow_language="QVTO",
    generated_tests_dir="qvto",
    snippets_dir="QVTO_test_generation",
    test_project_dir="QVT-O_Test",
)

REACTIONS_CONFIG = LanguageConfig(
    language=LANGUAGE_REACTIONS,
    workflow_language="Reactions",
    generated_tests_dir="reactions",
    snippets_dir="Reactions_test_generation",
    test_project_dir="Reactions_Language_Tests",
)

LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    config.language_key: config
    for config in (ETL_CONFIG, ATL_CONFIG, QVTO_CONFIG, REACTIONS_CONFIG)
}


class UnsupportedLanguageError(KeyError):
    """Raised when a language has no established filesystem conventions yet."""


def language_config(language: str) -> LanguageConfig:
    try:
        return LANGUAGE_CONFIGS[language.lower()]
    except KeyError as exc:
        known = ", ".join(sorted(LANGUAGE_CONFIGS))
        raise UnsupportedLanguageError(
            f"no filesystem conventions for language '{language}' (established: {known})"
        ) from exc


def test_generation_root() -> Path:
    # v5 final cleanup: generated test suites and their metrics are OUTPUT; they now
    # live under artifacts/work/ (the old nested Test_Generation dir is retired).
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "test_generation"


def _n8n_tests_root() -> Path:
    # v5 migration (Stage 3): the test-generation n8n tree moved to workflows/n8n/tests.
    from llm4mtl.paths import TARGET

    return TARGET.workflows / "tests"


def generated_test_artifacts_root(config: LanguageConfig) -> Path:
    """Generated n8n prompts and raw model responses for one language."""

    return test_generation_root() / config.language_key


def n8n_workflows_root(config: LanguageConfig) -> Path:
    return _n8n_tests_root() / "workflows" / f"{config.language_key}_variants"


def default_responses_root(config: LanguageConfig) -> Path:
    return generated_test_artifacts_root(config) / "responses"


def default_generated_tests_root(config: LanguageConfig) -> Path:
    return test_generation_root() / "generated_tests" / config.generated_tests_dir


def task_prompt_candidates_root(config: LanguageConfig) -> Path:
    """Where n8n writes unreviewed prompt candidates, one directory per model.

    Replaces the pre-v5 ``<lang>/prompts/<model>/`` tree, which no writer has
    targeted since prompt generation moved to n8n.
    """
    from llm4mtl.paths import TARGET

    return TARGET.artifacts_work / "task_prompt_candidates" / config.language_key


def frozen_task_prompt(config: LanguageConfig, task: str) -> Path:
    """The one reviewed prompt both generators consume for ``task``.

    Single definition on purpose: this path is the join between the reviewed
    benchmark input, the run's provenance hash, and the metadata of every suite
    generated from it, and those three must never disagree.
    """
    from llm4mtl.paths import TARGET

    return TARGET.prompt_assets / "task_prompts" / config.language_key / f"{task}.txt"


def _benchmark_tasks_root(config: LanguageConfig) -> Path:
    # v5 migration (Stage 3): hand-authored task inputs (references, task contracts)
    # moved out of the n8n tree into benchmark/tasks/<lang>/.
    from llm4mtl.paths import TARGET

    return TARGET.benchmark / "tasks" / config.language_key


def default_task_contracts_root(config: LanguageConfig) -> Path:
    return _benchmark_tasks_root(config) / "task_contracts"


def default_references_root(config: LanguageConfig) -> Path:
    return _benchmark_tasks_root(config) / "references"


def default_reactions_metamodels_root() -> Path:
    """Metamodel corpus accepted by the frozen standalone Reactions parser."""
    from llm4mtl.paths import TARGET

    return (
        TARGET.benchmark
        / "metamodels"
        / "additional_models"
        / "Reaction_model"
    )


def default_test_project_dir(config: LanguageConfig) -> Path:
    # v5 migration (Stage 2): the test-harness engine moved to engines/<lang>/harness.
    from llm4mtl.paths import TARGET

    return TARGET.engine_harness(config.language_key)


def default_results_root(config: LanguageConfig) -> Path:
    return test_generation_root() / "results" / config.generated_tests_dir
