"""Promotion of reference-validated suites."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from llm4mtl.conventions import relative_or_absolute
from llm4mtl.semantic_tests.suites.models import CandidateSuite


def promote_validated_suite(suite: CandidateSuite, row: dict[str, str]) -> Path:
    destination = validated_suite_path(suite)
    copy_suite_files(suite.path, destination)
    write_reference_validation_metadata(destination, suite, row)
    return destination


def promote_invalid_suite(suite: CandidateSuite, row: dict[str, str]) -> Path:
    destination = invalid_suite_path(suite)
    copy_suite_files(suite.path, destination)
    write_reference_validation_metadata(destination, suite, row)
    return destination


def validated_suite_path(suite: CandidateSuite) -> Path:
    return (
        suite.path.parents[3]
        / "validated"
        / suite.llm
        / suite.strategy
        / suite.suite_id
    )


def invalid_suite_path(suite: CandidateSuite) -> Path:
    return (
        suite.path.parents[3]
        / "invalid"
        / suite.llm
        / suite.strategy
        / suite.suite_id
    )


def copy_suite_files(source: Path, destination: Path) -> None:
    for source_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)


def write_reference_validation_metadata(
    destination: Path,
    suite: CandidateSuite,
    row: dict[str, str],
) -> None:
    metadata_path = destination / "reference_validation.json"
    payload = {
        "task": suite.task,
        "llm": suite.llm,
        "strategy": suite.strategy,
        "suite_id": suite.suite_id,
        "source_suite": relative_or_absolute(suite.path),
        "validation": row,
    }
    metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
