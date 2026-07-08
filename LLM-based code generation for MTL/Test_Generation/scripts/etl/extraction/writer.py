"""Filesystem writing and metadata construction for extracted suites."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from common.paths import ETL_CONFIG, default_prompts_root, n8n_workflows_root, relative_or_absolute
from etl.extraction.models import LANGUAGE, ResponseTarget
from etl.extraction.parser import java_files, model_files, semantic_case_files
from etl.extraction.semantic_cases import EnforcementOutcome, augment_with_generated_java


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
) -> tuple[Path, EnforcementOutcome]:
    extracted, enforcement = augment_with_generated_java(target.task, extracted)
    strategy_dir = (
        args.generated_tests_root.resolve()
        / target.task
        / "candidates"
        / target.llm
        / target.strategy
    )
    suite_id = args.suite_id or next_suite_id(strategy_dir)
    suite_dir = strategy_dir / suite_id

    if suite_dir.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Target suite already exists: {suite_dir}. Use --overwrite or --suite-id."
            )
        if not args.dry_run:
            shutil.rmtree(suite_dir)

    if args.dry_run:
        return suite_dir, enforcement

    suite_dir.mkdir(parents=True, exist_ok=True)
    for relative_path, content in extracted.items():
        output_path = suite_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    metadata = build_metadata(target, suite_id, extracted, enforcement)
    (suite_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return suite_dir, enforcement


def build_metadata(
    target: ResponseTarget,
    suite_id: str,
    extracted: dict[str, str],
    enforcement: EnforcementOutcome,
) -> dict[str, object]:
    prompt_path = default_prompts_root() / target.llm / f"{target.task}.txt"
    workflow_path = (
        n8n_workflows_root(ETL_CONFIG)
        / "test_generation"
        / f"Prompting_tests_{ETL_CONFIG.language}_{target.llm}_{target.strategy}.json"
    )
    return {
        "language": LANGUAGE,
        "task": target.task,
        "llm": target.llm,
        "strategy": target.strategy,
        "suite_id": suite_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_file": relative_or_absolute(prompt_path) if prompt_path.exists() else None,
        "workflow_file": relative_or_absolute(workflow_path) if workflow_path.exists() else None,
        "raw_output_file": relative_or_absolute(target.response_path),
        "status": "candidate" if enforcement.valid else "invalid",
        "contract_enforcement": {
            "applied": enforcement.applied,
            "valid": enforcement.valid,
            "violations": enforcement.violations,
        },
        "extraction": {
            "complete": bool(java_files(extracted)),
            "missing_files": [] if java_files(extracted) else ["*.java"],
            "extracted_files": sorted(extracted),
            "java_files": java_files(extracted),
            "semantic_case_files": semantic_case_files(extracted),
            "model_files": model_files(extracted),
        },
    }
