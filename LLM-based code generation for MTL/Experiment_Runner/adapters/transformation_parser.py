"""Adapter for ETL parser syntax validation."""

from __future__ import annotations

import json
from pathlib import Path

from Experiment_Runner.adapters.base import hash_paths, python_command, run_command
from Experiment_Runner.adapters.transformation_validation import TransformationValidationAdapter
from Experiment_Runner.models import PipelineConfig, StageResult


class TransformationParserAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.selector = TransformationValidationAdapter(repo_root)
        self.script = self.repo_root / "ETL_Parser" / "validate_etl_syntax.py"

    def parse(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        transformations = self.selector.select_transformations(config)
        input_hash = hash_paths(transformations)
        details = {"transformations": [str(path) for path in transformations]}
        if not transformations:
            return StageResult("transformation_parsing", "error", {"selected": 0, "failed": 1}, details, input_hash)
        if dry_run:
            return StageResult(
                "transformation_parsing",
                "dry_run",
                {"selected": len(transformations)},
                details,
                input_hash,
            )

        command = python_command(self.script)
        for transformation in transformations:
            command.extend(("--transformation", str(transformation)))
        command.extend(("--output-format", "json"))
        execution = run_command(command, self.repo_root, config.verbose)
        try:
            payload = json.loads(execution.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            payload = {}
        counts = {
            "selected": int(payload.get("selected", len(transformations))),
            "passed": int(payload.get("passed", 0)),
            "failed": int(payload.get("failed", 0)),
        }
        details.update(
            command=command,
            stdout=execution.stdout,
            stderr=execution.stderr,
            results_file=payload.get("results_file"),
            passed_transformations=payload.get("passed_transformations", []),
            failed_transformations=payload.get("failed_transformations", []),
        )
        status = "completed" if payload.get("status") == "completed" else "infrastructure_error"
        return StageResult(
            "transformation_parsing",
            status,
            counts,
            details,
            input_hash,
            exit_code=execution.exit_code,
        )
