"""Input selection and input hashing shared by the stages.

Also the result a stage returns when it selected nothing to work on.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from llm4mtl.semantic_tests.suites.discovery import (
    candidate_identity,
    candidate_suite_directories,
    matches_selection,
)
from llm4mtl.stages.models import ConfigError, PipelineConfig, StageResult


def _path_hash_chunks(path: Path) -> Iterator[bytes]:
    name = str(path).encode("utf-8")
    yield len(name).to_bytes(8, "big")
    yield name
    if path.is_file():
        yield path.read_bytes()
        return
    if not path.is_dir():
        return

    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    for child in files:
        yield str(child.relative_to(path)).encode("utf-8")
        yield child.read_bytes()


def hash_paths(paths: list[Path]) -> str:
    """Hash selected files and directory contents in deterministic path order."""
    digest = hashlib.sha256()
    for path in sorted({item.resolve() for item in paths}):
        for chunk in _path_hash_chunks(path):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_selection(axis: str, values: list[str]) -> set[str]:
    """The values a stage may select for one identity axis.

    Never falls back to "every known value": a stage that selected the whole
    matrix would produce results attributed to a run whose identity names one
    combination.
    """
    if not values:
        raise ConfigError(
            f"this stage needs the run's {axis}, but the run fixed none. "
            "Select it explicitly instead of running against every value."
        )
    return set(values)


def existing_files(paths: list[str]) -> list[Path]:
    """The given paths that are files, resolved and sorted."""
    return sorted(Path(path).resolve() for path in paths if Path(path).is_file())


def select_generated_files(
    root: Path,
    extension: str,
    config: PipelineConfig,
    *,
    models: set[str],
    strategies: set[str],
) -> list[Path]:
    """Files filed as ``<model>/<strategy>/<task>.<extension>`` below ``root``."""
    tasks = set(config.tasks)
    return sorted(
        path.resolve()
        for path in root.glob(f"*/*/*.{extension}")
        if path.parent.parent.name in models
        and path.parent.name in strategies
        and path.stem in tasks
    )


def select_candidate_suites(
    config: PipelineConfig,
    generated_tests_root: Path,
) -> list[Path]:
    """Candidate suite directories this stage was asked to judge.

    The suites are read from the shared ``generated_tests_root`` tree and
    filtered by the run's task, test model, test strategy and, when set, suite
    id.
    """
    tasks = set(config.tasks)
    models = fixed_selection("test-generation model", config.test_models)
    strategies = fixed_selection("strategy", config.test_strategies)
    return sorted(
        path
        for path in candidate_suite_directories(generated_tests_root)
        if matches_selection(
            candidate_identity(path),
            tasks=tasks,
            models=models,
            strategies=strategies,
            suite_id=config.suite_id,
        )
    )


def nothing_selected_result(
    name: str,
    details: dict[str, object],
    input_hash: str,
) -> StageResult:
    """The result of a stage that found no input: an error with one failure."""
    return StageResult(name, "error", {"selected": 0, "failed": 1}, details, input_hash)
