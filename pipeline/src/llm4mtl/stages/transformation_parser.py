"""Syntax validation of generated transformations, through the language adapter."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.domain import ParseObservation
from llm4mtl.languages import language_adapter
from llm4mtl.run_store.models import RunPaths
from llm4mtl.semantic_tests.validation import workspace_for
from llm4mtl.stages.models import (
    TRANSFORMATION_PARSING_STAGE_NAME,
    ConfigError,
    PipelineConfig,
    StageResult,
)
from llm4mtl.stages.selection import (
    dry_run_result,
    hash_paths,
    nothing_selected_result,
)
from llm4mtl.stages.transformation_validation import (
    TransformationValidationAdapter,
)
from llm4mtl.vocabulary import SYNTAX_VALIDATION_STAGE_ID


class TransformationParserAdapter:
    """Select and parse generated transformations in a run-local workspace."""

    def __init__(self) -> None:
        self.selector = TransformationValidationAdapter()

    def parse(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        transformations = self.selector.select_transformations(config)
        input_hash = hash_paths(transformations)
        details: dict[str, object] = {
            "transformations": [str(path) for path in transformations]
        }
        if not transformations:
            return nothing_selected_result(
                TRANSFORMATION_PARSING_STAGE_NAME, details, input_hash
            )
        if dry_run:
            return dry_run_result(
                TRANSFORMATION_PARSING_STAGE_NAME,
                len(transformations),
                details,
                input_hash,
            )

        observations = self._parse_in_run_workspace(config, transformations)
        passed = [path for path in transformations if observations[path].parsed]
        failed = [path for path in transformations if not observations[path].parsed]
        details.update(_parse_details(transformations, observations, passed, failed))
        return StageResult(
            TRANSFORMATION_PARSING_STAGE_NAME,
            "completed",
            {
                "selected": len(transformations),
                "passed": len(passed),
                "failed": len(failed),
            },
            details,
            input_hash,
        )

    @staticmethod
    def _parse_in_run_workspace(
        config: PipelineConfig,
        transformations: list[Path],
    ) -> dict[Path, ParseObservation]:
        """Parse every transformation, keeping the evidence inside the run."""
        if not config.run_dir:
            raise ConfigError(
                "transformation parsing requires a resolved run directory for evidence"
            )
        run_dir = Path(config.run_dir).resolve()
        adapter = language_adapter(config.language)
        engine_dir = (
            Path(config.engine_dir).resolve()
            if config.engine_dir
            else RunPaths(run_dir).workspaces_dir / config.language
        )
        workspace = workspace_for(
            engine_dir,
            RunPaths(run_dir).observations_dir / SYNTAX_VALIDATION_STAGE_ID,
        )
        return adapter.parse_transformations(transformations, workspace)


def _parse_details(
    transformations: list[Path],
    observations: dict[Path, ParseObservation],
    passed: list[Path],
    failed: list[Path],
) -> dict[str, object]:
    return {
        "passed_transformations": [str(path) for path in passed],
        "failed_transformations": [str(path) for path in failed],
        # Every selected transformation appears, so a missing count shows as
        # `null`, never as absent or as a measured 0 that an errors-per-LOC
        # figure would wrongly use.
        "problem_counts": {
            str(path): observations[path].problem_count for path in transformations
        },
        "diagnostics": {
            str(path): observations[path].diagnostic
            for path in failed
            if observations[path].diagnostic
        },
    }
