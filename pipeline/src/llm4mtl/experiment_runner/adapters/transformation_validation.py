"""Execution of validated suites against generated transformations.

This stage asks a different question from reference validation. There the
transformation is trusted, so anything the engine rejects is a broken test.
Here the transformation is the artifact under test, so an engine that refuses it
is evidence about the transformation — while a suite-side problem (nothing
compiled, no model loaded) still means the transformation was never judged.
Interpreting the same observation differently for the two roles is what keeps
the populations from contaminating each other.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from llm4mtl.conventions import (
    default_generated_tests_root,
    language_config,
)
from llm4mtl.domain import OutcomeStatus, SuiteExecutionObservation, TransformationOutcome
from llm4mtl.experiment_runner.adapters.base import fixed_selection, hash_paths
from llm4mtl.experiment_runner.config import ConfigError
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.languages import language_adapter
from llm4mtl.semantic_tests.suite_execution import read_observation
from llm4mtl.semantic_tests.suites.discovery import suite_from_path
from llm4mtl.semantic_tests.validation import workspace_for

DEFAULT_PAIR_TIMEOUT_SECONDS = 240

class TransformationValidationAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    @staticmethod
    def validated_tests_root(config: PipelineConfig) -> Path:
        return default_generated_tests_root(language_config(config.language))

    @staticmethod
    def transformations_root(config: PipelineConfig) -> Path:
        from llm4mtl.paths import TARGET

        return (
            TARGET.artifacts_work
            / "transformation_generation"
            / language_config(config.language).language_key
            / "responses"
        )

    def semantic_validation(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        if config.transformation_selection_locked and not config.transformations:
            # The parser passed nothing on: there is nothing to judge, and
            # selecting suites for it would only invent work.
            return StageResult(
                "transformation_validation",
                "skipped",
                {"selected_suites": 0, "selected_transformations": 0, "execution_pairs": 0, "skipped": 1},
                {"skip_reason": "SKIPPED_NO_PARSED_TRANSFORMATIONS"},
            )

        suites = self.select_validated_suites(config, require_observation=not dry_run)
        transformations = self.select_transformations(config)
        pairs = [
            (suite, transformation)
            for suite in suites
            for transformation in transformations
            if suite.parts[-5] == transformation.stem
        ]
        input_hash = hash_paths(suites + transformations)
        suite_detail_key = (
            "suite_candidates_awaiting_reference_validation"
            if dry_run
            else "reference_validated_suites"
        )
        details: dict[str, object] = {
            suite_detail_key: [str(path) for path in suites],
            "transformations": [str(path) for path in transformations],
        }
        counts = {
            "selected_suites": len(suites),
            "selected_transformations": len(transformations),
            "execution_pairs": len(pairs),
        }
        if not pairs:
            counts["failed"] = 1
            return StageResult("transformation_validation", "error", counts, details, input_hash)
        if dry_run:
            return StageResult("transformation_validation", "dry_run", counts, details, input_hash)

        adapter = language_adapter(config.language)
        if not config.engine_dir:
            raise ConfigError(
                "transformation execution requires a run-local engine workspace"
            )
        engine_dir = Path(config.engine_dir)
        workspace = workspace_for(engine_dir, engine_dir)

        observed: list[
            tuple[Path, Path, SuiteExecutionObservation, TransformationOutcome | None]
        ] = []
        for suite_path, transformation in pairs:
            suite = suite_from_path(
                suite_path,
                self.validated_tests_root(config),
                config.language,
            )
            observation = adapter.execute_suite(
                suite, transformation, workspace, DEFAULT_PAIR_TIMEOUT_SECONDS
            )
            failure_outcome = adapter.normalize_transformation_failure(observation)
            observed.append((suite_path, transformation, observation, failure_outcome))

        counts.update(
            execution_counts(
                (observation, failure_outcome)
                for _, _, observation, failure_outcome in observed
            )
        )
        details["pairs"] = [
            {
                "suite": str(suite_path),
                "transformation": str(transformation),
                "assertions_passed": observation.assertions_passed,
                "failure_stage": observation.failure_stage,
                "outcome_status": (
                    failure_outcome.status.value if failure_outcome is not None else None
                ),
            }
            for suite_path, transformation, observation, failure_outcome in observed
        ]
        return StageResult("transformation_validation", "completed", counts, details, input_hash)

    def select_validated_suites(
        self,
        config: PipelineConfig,
        *,
        require_observation: bool = True,
    ) -> list[Path]:
        """Suites reference-validated by this run, never by a copied directory."""
        if config.suites:
            candidates = sorted(
                Path(path).resolve()
                for path in config.suites
                if Path(path).is_dir() and "candidates" in Path(path).parts
            )
        else:
            tasks = set(config.tasks)
            models = fixed_selection("test-generation model", config.test_models)
            strategies = fixed_selection("strategy", config.test_strategies)
            candidates = sorted(
                path.resolve()
                for path in self.validated_tests_root(config).glob(
                    "*/candidates/*/*/suite_*"
                )
                if path.is_dir()
                and path.parts[-3] in models
                and path.parts[-2] in strategies
                and (config.all_tasks or path.parts[-5] in tasks)
                and (not config.suite_id or path.name == config.suite_id)
            )

        if not require_observation:
            # A dry-run plans the candidates that can become eligible after the
            # earlier reference stage; it does not claim they already passed.
            return candidates

        adapter = language_adapter(config.language)
        observations_root = self._observations_root(config)
        validated: list[Path] = []
        for path in candidates:
            suite = suite_from_path(
                path,
                self.validated_tests_root(config),
                config.language,
            )
            reference = adapter.reference_transformation(suite.task)
            observation = read_observation(
                observations_root,
                suite,
                reference,
            )
            if (
                observation is not None
                and observation.is_technically_executable
                and observation.assertions_passed
            ):
                validated.append(path)
        return validated

    @staticmethod
    def _observations_root(config: PipelineConfig) -> Path:
        if not config.run_dir:
            raise ConfigError(
                "a resolved run directory is required to select "
                "reference-validated suites"
            )
        return Path(config.run_dir).resolve() / "observations"

    def select_transformations(self, config: PipelineConfig) -> list[Path]:
        if config.transformations or config.transformation_selection_locked:
            return sorted(
                Path(path).resolve() for path in config.transformations if Path(path).is_file()
            )
        tasks = set(config.tasks)
        models = fixed_selection("transformation model", config.transformation_models)
        strategies = fixed_selection("strategy", config.transformation_strategies)
        extension = language_config(config.language).language_key
        return sorted(
            path.resolve()
            for path in self.transformations_root(config).glob(f"*/*/*.{extension}")
            if path.parent.parent.name in models
            and path.parent.name in strategies
            and (config.all_tasks or path.stem in tasks)
        )


def execution_counts(
    observations: Iterable[
        tuple[SuiteExecutionObservation, TransformationOutcome | None]
    ],
) -> dict[str, int]:
    """Count pairs by what the run established about the transformation."""
    passed = failed = skipped = infrastructure = 0
    for observation, failure_outcome in observations:
        if failure_outcome is not None and failure_outcome.status in {
            OutcomeStatus.TIMED_OUT,
            OutcomeStatus.INFRASTRUCTURE_FAILED,
        }:
            infrastructure += 1
        elif observation.assertions_passed:
            passed += 1
        elif observation.failure_stage == "assertion_failure":
            failed += 1
        elif (
            failure_outcome is not None
            and failure_outcome.status.is_attributable_to_the_transformation
        ):
            failed += 1
        else:
            # A suite-side problem: the transformation was never judged.
            skipped += 1
    return {
        "evaluated": passed + failed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "infrastructure_errors": infrastructure,
    }
