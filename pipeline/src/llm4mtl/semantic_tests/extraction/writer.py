"""Filesystem writing and metadata construction for extracted suites."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from llm4mtl.conventions import (
    LanguageConfig,
    frozen_task_prompt,
    language_config,
    n8n_workflows_root,
)
from llm4mtl.domain import ArtifactValidation
from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.paths import repository_relative
from llm4mtl.run_store.identity import resolve_contained_dir
from llm4mtl.semantic_tests.extraction.models import (
    ExtractionOptions,
    ResponseTarget,
    SuiteExistsError,
)
from llm4mtl.semantic_tests.extraction.parser import (
    java_files,
    model_files,
    semantic_case_files,
)
from llm4mtl.semantic_tests.suites.discovery import CANDIDATES_DIRECTORY
from llm4mtl.semantic_tests.suites.metadata import SUITE_METADATA_FILE


def next_suite_id(strategy_dir: Path) -> str:
    """Return the next deterministic candidate id below ``strategy_dir``."""
    max_seen = 0
    for child in strategy_dir.iterdir() if strategy_dir.exists() else []:
        if not child.is_dir():
            continue
        match = re.fullmatch(r"suite_(\d+)", child.name)
        if match:
            max_seen = max(max_seen, int(match.group(1)))
    return f"suite_{max_seen + 1:03d}"


def allocate_suite_dir(target: ResponseTarget, options: ExtractionOptions) -> Path:
    """Claim the candidate directory for this response, without writing to it."""
    strategy_dir = (
        options.generated_tests_root.resolve()
        / target.task
        / CANDIDATES_DIRECTORY
        / target.llm
        / target.strategy
    )
    suite_id = options.suite_id or next_suite_id(strategy_dir)
    suite_dir = resolve_contained_dir(strategy_dir, suite_id, kind="suite")

    if suite_dir.exists():
        raise SuiteExistsError(
            f"Target suite already exists and is immutable: {suite_dir}. "
            "Choose a new suite id; an existing candidate is never replaced."
        )
    return suite_dir


def write_failed_candidate(
    target: ResponseTarget,
    options: ExtractionOptions,
    adapter: LanguageAdapter,
    *,
    reason_code: str,
    violations: tuple[str, ...],
) -> tuple[Path, ArtifactValidation]:
    """Record a response whose artifacts could not be read, inventing nothing.

    A response that fails extraction is still a generated test the experiment
    asked for, so it must stay countable. Without a candidate directory it would
    vanish from every later stage, and the invalid-test rate would silently
    ignore the weakest responses.

    The directory holds metadata only: no ``semantic_cases.json``, no models, no
    harness. There is nothing to write them from, and a placeholder would be a
    made-up artifact. The recorded verdict is invalid, so validation refuses the
    suite before Maven and it never becomes a runtime failure.
    """
    validation = ArtifactValidation(
        valid=False,
        reason_code=reason_code,
        violations=violations,
    )
    suite_dir = allocate_suite_dir(target, options)
    if options.dry_run:
        return suite_dir, validation

    suite_dir.mkdir(parents=True, exist_ok=True)
    metadata = build_metadata(target, suite_dir.name, {}, validation, adapter)
    _write_metadata(suite_dir, metadata)
    return suite_dir, validation


def write_suite(
    target: ResponseTarget,
    extracted: dict[str, str],
    options: ExtractionOptions,
    adapter: LanguageAdapter,
) -> tuple[Path, ArtifactValidation]:
    """Render and persist one immutable generated-suite candidate."""
    extracted, validation = adapter.render_suite_artifacts(target.task, extracted)
    suite_dir = allocate_suite_dir(target, options)
    suite_id = suite_dir.name

    if options.dry_run:
        return suite_dir, validation

    suite_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in extracted.items():
        output_path = suite_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    metadata = build_metadata(target, suite_id, extracted, validation, adapter)
    _write_metadata(suite_dir, metadata)
    return suite_dir, validation


def _write_metadata(suite_dir: Path, metadata: dict[str, object]) -> None:
    (suite_dir / SUITE_METADATA_FILE).write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def build_metadata(
    target: ResponseTarget,
    suite_id: str,
    extracted: dict[str, str],
    validation: ArtifactValidation,
    adapter: LanguageAdapter,
) -> dict[str, object]:
    """Build provenance and artifact metadata for one candidate suite."""
    config = language_config(adapter.language_id)
    return {
        "language": adapter.language_id,
        "task": target.task,
        "llm": target.llm,
        "strategy": target.strategy,
        "suite_id": suite_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # The reviewed, frozen prompt is the one both generators actually consumed.
        "prompt_file": _repository_path_if_present(
            frozen_task_prompt(config, target.task)
        ),
        "workflow_file": _repository_path_if_present(
            _test_generation_workflow(config, target)
        ),
        "raw_output_file": repository_relative(target.response_path),
        "status": "candidate" if validation.valid else "invalid",
        "artifact_validation": validation.as_metadata(),
        "extraction": _extraction_summary(extracted),
    }


def _test_generation_workflow(config: LanguageConfig, target: ResponseTarget) -> Path:
    """The exported n8n workflow that generates tests for this model and strategy."""
    file_name = (
        f"Prompting_tests_{config.workflow_language}_"
        f"{target.llm}_{target.strategy}.json"
    )
    return n8n_workflows_root(config) / "test_generation" / file_name


def _repository_path_if_present(path: Path) -> str | None:
    return repository_relative(path) if path.exists() else None


def _extraction_summary(extracted: dict[str, str]) -> dict[str, list[str]]:
    return {
        "extracted_files": sorted(extracted),
        "java_files": java_files(extracted),
        "semantic_case_files": semantic_case_files(extracted),
        "model_files": model_files(extracted),
    }
