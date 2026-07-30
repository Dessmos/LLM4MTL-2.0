"""Filesystem writing and metadata construction for extracted suites."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from llm4mtl.conventions import (
    frozen_task_prompt,
    language_config,
    n8n_workflows_root,
    relative_or_absolute,
)
from llm4mtl.domain import ArtifactValidation
from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.run_store.identity import resolve_contained_dir
from llm4mtl.semantic_tests.extraction.models import ResponseTarget
from llm4mtl.semantic_tests.extraction.parser import java_files, model_files, semantic_case_files


def next_suite_id(strategy_dir: Path) -> str:
    max_seen = 0
    for child in strategy_dir.iterdir() if strategy_dir.exists() else []:
        if not child.is_dir():
            continue
        match = re.fullmatch(r"suite_(\d+)", child.name)
        if match:
            max_seen = max(max_seen, int(match.group(1)))
    return f"suite_{max_seen + 1:03d}"


def write_suite(
    target: ResponseTarget,
    extracted: dict[str, str],
    args: argparse.Namespace,
    adapter: LanguageAdapter,
) -> tuple[Path, ArtifactValidation]:
    extracted, validation = adapter.render_suite_artifacts(target.task, extracted)
    strategy_dir = (
        args.generated_tests_root.resolve()
        / target.task
        / "candidates"
        / target.llm
        / target.strategy
    )
    suite_id = args.suite_id or next_suite_id(strategy_dir)
    suite_dir = resolve_contained_dir(strategy_dir, suite_id, kind="suite")

    if suite_dir.exists():
        raise SystemExit(
            f"Target suite already exists and is immutable: {suite_dir}. "
            "Choose a new --suite-id; --overwrite cannot replace scientific evidence."
        )

    if args.dry_run:
        return suite_dir, validation

    suite_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in extracted.items():
        output_path = suite_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    metadata = build_metadata(target, suite_id, extracted, validation, adapter)
    (suite_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite_dir, validation


def build_metadata(
    target: ResponseTarget,
    suite_id: str,
    extracted: dict[str, str],
    validation: ArtifactValidation,
    adapter: LanguageAdapter,
) -> dict[str, object]:
    config = language_config(adapter.language_id)
    # The reviewed, frozen prompt is the one both generators actually consumed.
    # This used to name a pre-v5 per-model prompt directory that no longer
    # exists, so every suite recorded prompt_file: null.
    prompt_path = frozen_task_prompt(config, target.task)
    workflow_path = (
        n8n_workflows_root(config)
        / "test_generation"
        / (
            f"Prompting_tests_{config.workflow_language}_"
            f"{target.llm}_{target.strategy}.json"
        )
    )
    return {
        "language": adapter.language_id,
        "task": target.task,
        "llm": target.llm,
        "strategy": target.strategy,
        "suite_id": suite_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_file": relative_or_absolute(prompt_path) if prompt_path.exists() else None,
        "workflow_file": relative_or_absolute(workflow_path) if workflow_path.exists() else None,
        "raw_output_file": relative_or_absolute(target.response_path),
        "status": "candidate" if validation.valid else "invalid",
        "artifact_validation": validation.as_metadata(),
        "extraction": {
            "extracted_files": sorted(extracted),
            "java_files": java_files(extracted),
            "semantic_case_files": semantic_case_files(extracted),
            "model_files": model_files(extracted),
        },
    }
