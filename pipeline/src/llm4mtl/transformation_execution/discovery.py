"""Discover run-validated candidate suites and generated ETL transformations."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.semantic_tests.suites.discovery import candidate_suite_directories
from llm4mtl.transformation_execution.models import (
    GeneratedTransformation,
    ValidatedSuite,
    ValidationPair,
)


def discover_validated_suites(
    root: Path,
    observations_root: Path,
    explicit: list[Path] | None = None,
    task: str | None = None,
    llm: str | None = None,
    strategy: str | None = None,
) -> list[ValidatedSuite]:
    """Candidates whose reference-valid observation belongs to this run."""
    root = root.resolve()
    paths = (
        [path.resolve() for path in explicit]
        if explicit
        else candidate_suite_directories(root)
    )
    suites = [candidate_suite_from_path(path, root) for path in paths if path.is_dir()]
    selected = [
        suite for suite in suites if _matches_identity(suite, task, llm, strategy)
    ]
    return _reference_validated_suites(selected, observations_root)


def _reference_validated_suites(
    suites: list[ValidatedSuite],
    observations_root: Path,
) -> list[ValidatedSuite]:
    # Deferred to break the language adapter -> suite execution -> legacy
    # transformation facade import cycle.
    from llm4mtl.languages import language_adapter
    from llm4mtl.semantic_tests.suite_execution import read_observation

    adapter = language_adapter("etl")
    resolved_observations_root = observations_root.resolve()
    validated = []
    for suite in suites:
        observation = read_observation(
            resolved_observations_root,
            suite.as_candidate(),
            adapter.reference_transformation(suite.task),
        )
        if observation is not None and observation.is_reference_valid:
            validated.append(suite)
    return validated


def candidate_suite_from_path(path: Path, root: Path) -> ValidatedSuite:
    path = path.resolve()
    try:
        rel = path.relative_to(root.resolve())
    except ValueError:
        rel = None

    if rel and len(rel.parts) >= 5 and rel.parts[1] == "candidates":
        task, _, llm, strategy, suite_id = rel.parts[:5]
    else:
        parts = path.parts
        try:
            idx = parts.index("candidates")
            task = parts[idx - 1]
            llm = parts[idx + 1]
            strategy = parts[idx + 2]
            suite_id = parts[idx + 3]
        except (ValueError, IndexError):
            raise SystemExit(f"Cannot infer candidate suite metadata from {path}")

    return ValidatedSuite(
        path=path, task=task, llm=llm, strategy=strategy, suite_id=suite_id
    )


def discover_transformations(
    root: Path,
    explicit: list[Path] | None = None,
    task: str | None = None,
    llm: str | None = None,
    strategy: str | None = None,
) -> list[GeneratedTransformation]:
    root = root.resolve()
    paths = (
        [path.resolve() for path in explicit]
        if explicit
        else sorted(root.glob("*/*/*.etl"))
    )
    transformations = [
        generated_transformation_from_path(path, root)
        for path in paths
        if path.is_file()
    ]
    return [
        transformation
        for transformation in transformations
        if _matches_identity(transformation, task, llm, strategy)
    ]


def _matches_identity(
    candidate: ValidatedSuite | GeneratedTransformation,
    task: str | None,
    llm: str | None,
    strategy: str | None,
) -> bool:
    return (
        (not task or candidate.task == task)
        and (not llm or candidate.llm == llm)
        and (not strategy or candidate.strategy == strategy)
    )


def generated_transformation_from_path(
    path: Path, root: Path
) -> GeneratedTransformation:
    path = path.resolve()
    try:
        rel = path.relative_to(root.resolve())
    except ValueError:
        rel = None

    if rel and len(rel.parts) >= 3:
        llm, strategy = rel.parts[:2]
    else:
        try:
            strategy = path.parent.name
            llm = path.parent.parent.name
        except IndexError:
            raise SystemExit(
                f"Cannot infer generated transformation metadata from {path}"
            )

    return GeneratedTransformation(
        path=path, task=path.stem, llm=llm, strategy=strategy
    )


def match_pairs(
    suites: list[ValidatedSuite],
    transformations: list[GeneratedTransformation],
) -> list[ValidationPair]:
    return [
        ValidationPair(suite=suite, transformation=transformation)
        for suite in suites
        for transformation in transformations
        if suite.task == transformation.task
    ]
