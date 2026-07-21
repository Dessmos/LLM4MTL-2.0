"""Discover validated suites and generated ETL transformations."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.transformation_execution.models import (
    GeneratedTransformation,
    ValidatedSuite,
    ValidationPair,
)


def discover_validated_suites(
    root: Path,
    explicit: list[Path] | None = None,
    task: str | None = None,
    llm: str | None = None,
    strategy: str | None = None,
) -> list[ValidatedSuite]:
    root = root.resolve()
    paths = [path.resolve() for path in explicit] if explicit else sorted(root.glob("*/validated/*/*/suite_*"))
    suites = [validated_suite_from_path(path, root) for path in paths if path.is_dir()]
    return [
        suite
        for suite in suites
        if (not task or suite.task == task)
        and (not llm or suite.llm == llm)
        and (not strategy or suite.strategy == strategy)
    ]


def validated_suite_from_path(path: Path, root: Path) -> ValidatedSuite:
    path = path.resolve()
    try:
        rel = path.relative_to(root.resolve())
    except ValueError:
        rel = None

    if rel and len(rel.parts) >= 5 and rel.parts[1] == "validated":
        task, _, llm, strategy, suite_id = rel.parts[:5]
    else:
        parts = path.parts
        try:
            idx = parts.index("validated")
            task = parts[idx - 1]
            llm = parts[idx + 1]
            strategy = parts[idx + 2]
            suite_id = parts[idx + 3]
        except (ValueError, IndexError):
            raise SystemExit(f"Cannot infer validated suite metadata from {path}")

    return ValidatedSuite(path=path, task=task, llm=llm, strategy=strategy, suite_id=suite_id)


def discover_transformations(
    root: Path,
    explicit: list[Path] | None = None,
    task: str | None = None,
    llm: str | None = None,
    strategy: str | None = None,
) -> list[GeneratedTransformation]:
    root = root.resolve()
    paths = [path.resolve() for path in explicit] if explicit else sorted(root.glob("*/*/*.etl"))
    transformations = [generated_transformation_from_path(path, root) for path in paths if path.is_file()]
    return [
        transformation
        for transformation in transformations
        if (not task or transformation.task == task)
        and (not llm or transformation.llm == llm)
        and (not strategy or transformation.strategy == strategy)
    ]


def generated_transformation_from_path(path: Path, root: Path) -> GeneratedTransformation:
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
            raise SystemExit(f"Cannot infer generated transformation metadata from {path}")

    return GeneratedTransformation(path=path, task=path.stem, llm=llm, strategy=strategy)


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
