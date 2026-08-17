"""Syntax validation of generated transformations, through the language adapter."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.experiment_runner.adapters.base import hash_paths
from llm4mtl.experiment_runner.adapters.transformation_validation import (
    TransformationValidationAdapter,
)
from llm4mtl.experiment_runner.config import ConfigError
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.languages import language_adapter
from llm4mtl.semantic_tests.validation import workspace_for


class TransformationParserAdapter:
    """Select and parse generated transformations in a run-local workspace."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.selector = TransformationValidationAdapter(repo_root)

    def parse(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        transformations = self.selector.select_transformations(config)
        input_hash = hash_paths(transformations)
        details: dict[str, object] = {
            "transformations": [str(path) for path in transformations]
        }
        if not transformations:
            return StageResult(
                "transformation_parsing",
                "error",
                {"selected": 0, "failed": 1},
                details,
                input_hash,
            )
        if dry_run:
            return StageResult(
                "transformation_parsing",
                "dry_run",
                {"selected": len(transformations)},
                details,
                input_hash,
            )

        if not config.run_dir:
            raise ConfigError(
                "transformation parsing requires a resolved run directory for evidence"
            )
        run_dir = Path(config.run_dir).resolve()
        adapter = language_adapter(config.language)
        workspace = workspace_for(
            Path(config.engine_dir).resolve()
            if config.engine_dir
            else run_dir / "workspaces" / config.language,
            run_dir / "observations" / "syntax-validation",
        )
        observations = adapter.parse_transformations(transformations, workspace)

        passed = [path for path in transformations if observations[path].parsed]
        failed = [path for path in transformations if not observations[path].parsed]
        details.update(
            passed_transformations=[str(path) for path in passed],
            failed_transformations=[str(path) for path in failed],
            # Every selected transformation appears, so a parser that reported no
            # count for one is visible as `null` rather than absent. Serialized
            # as JSON, that stays distinguishable from a measured 0 — which is
            # what any errors-per-LOC figure has to divide by.
            problem_counts={
                str(path): observations[path].problem_count for path in transformations
            },
            diagnostics={
                str(path): observations[path].diagnostic
                for path in failed
                if observations[path].diagnostic
            },
        )
        return StageResult(
            "transformation_parsing",
            "completed",
            {
                "selected": len(transformations),
                "passed": len(passed),
                "failed": len(failed),
            },
            details,
            input_hash,
        )
