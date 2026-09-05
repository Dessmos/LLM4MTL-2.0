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

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from llm4mtl.conventions import (
    default_generated_tests_root,
    language_config,
)
from llm4mtl.domain import (
    OutcomeStatus,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.experiment_runner.adapters.base import fixed_selection, hash_paths
from llm4mtl.experiment_runner.config import ConfigError
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.languages import LanguageAdapter, language_adapter
from llm4mtl.semantic_tests.suite_execution import (
    GENERATED_TRANSFORMATION_ROLE,
    observation_lock,
    observation_path,
    read_observation,
    record_observation,
)
from llm4mtl.semantic_tests.suites.discovery import (
    candidate_suite_directories,
    suite_from_path,
)
from llm4mtl.semantic_tests.validation import workspace_for
from llm4mtl.serialization.hashing import file_sha256

DEFAULT_PAIR_TIMEOUT_SECONDS = 240


def _matching_execution_pairs(
    suites: list[Path],
    transformations: list[Path],
) -> list[tuple[Path, Path]]:
    return [
        (suite, transformation)
        for suite in suites
        for transformation in transformations
        if suite.parts[-5] == transformation.stem
    ]


@dataclass(frozen=True)
class _ObservedExecutionPair:
    """One generated-transformation execution and its recorded evidence."""

    suite_path: Path
    transformation: Path
    observation: SuiteExecutionObservation
    failure_outcome: TransformationOutcome | None
    evidence_path: Path

    def to_detail(self) -> dict[str, object]:
        return {
            "suite": str(self.suite_path),
            "transformation": str(self.transformation),
            "assertions_passed": self.observation.assertions_passed,
            "failure_stage": self.observation.failure_stage,
            "outcome_status": (
                self.failure_outcome.status.value
                if self.failure_outcome is not None
                else None
            ),
            "evidence": str(self.evidence_path),
        }


class TransformationValidationAdapter:
    """Execute reference-valid suites against generated transformations."""

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
                {
                    "selected_suites": 0,
                    "selected_transformations": 0,
                    "execution_pairs": 0,
                    "skipped": 1,
                },
                {"skip_reason": "SKIPPED_NO_PARSED_TRANSFORMATIONS"},
            )

        suites = self.select_validated_suites(config, require_observation=not dry_run)
        transformations = self.select_transformations(config)
        pairs = _matching_execution_pairs(suites, transformations)
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
            return StageResult(
                "transformation_validation",
                "error",
                counts,
                details,
                input_hash,
            )
        if dry_run:
            return StageResult(
                "transformation_validation",
                "dry_run",
                counts,
                details,
                input_hash,
            )

        observed_pairs = self._execute_pairs(config, pairs)
        counts.update(
            execution_counts(
                (pair.observation, pair.failure_outcome) for pair in observed_pairs
            )
        )
        details["pairs"] = [pair.to_detail() for pair in observed_pairs]
        return StageResult(
            "transformation_validation",
            "completed",
            counts,
            details,
            input_hash,
        )

    def _execute_pairs(
        self,
        config: PipelineConfig,
        pairs: list[tuple[Path, Path]],
    ) -> list[_ObservedExecutionPair]:
        if not config.engine_dir:
            raise ConfigError(
                "transformation execution requires a run-local engine workspace"
            )

        adapter = language_adapter(config.language)
        engine_dir = Path(config.engine_dir)
        observations_root = self._observations_root(config)
        observed_pairs: list[_ObservedExecutionPair] = []
        for suite_path, transformation in pairs:
            suite = suite_from_path(
                suite_path,
                self.validated_tests_root(config),
                config.language,
            )
            pair_root = (
                observations_root
                / "generated_transformations"
                / file_sha256(transformation)
            )
            with observation_lock(pair_root, suite):
                observation = read_observation(
                    pair_root,
                    suite,
                    transformation,
                    transformation_role=GENERATED_TRANSFORMATION_ROLE,
                )
                if observation is None:
                    workspace = workspace_for(engine_dir, pair_root)
                    observation, raw_evidence = adapter.execute_suite(
                        suite,
                        transformation,
                        workspace,
                        DEFAULT_PAIR_TIMEOUT_SECONDS,
                    )
                    # Archived here, inside the per-pair lock: pair N+1 runs
                    # `mvn clean` in the same workspace and deletes the reports
                    # that explain pair N.
                    evidence_path = record_observation(
                        pair_root,
                        suite,
                        transformation,
                        observation,
                        transformation_role=GENERATED_TRANSFORMATION_ROLE,
                        evidence=raw_evidence,
                    )
                else:
                    evidence_path = observation_path(pair_root, suite)
            failure_outcome = adapter.normalize_transformation_failure(observation)
            observed_pairs.append(
                _ObservedExecutionPair(
                    suite_path=suite_path,
                    transformation=transformation,
                    observation=observation,
                    failure_outcome=failure_outcome,
                    evidence_path=evidence_path,
                )
            )
        return observed_pairs

    def select_validated_suites(
        self,
        config: PipelineConfig,
        *,
        require_observation: bool = True,
    ) -> list[Path]:
        """Suites reference-validated by this run, never by a copied directory."""
        candidates = self._select_candidate_suites(config)
        if not require_observation:
            # A dry-run plans the candidates that can become eligible after the
            # earlier reference stage; it does not claim they already passed.
            return candidates

        adapter = language_adapter(config.language)
        observations_root = self._observations_root(config)
        validated: list[Path] = []
        for path in candidates:
            if self._has_valid_reference_observation(
                path,
                config,
                adapter,
                observations_root,
            ):
                validated.append(path)
        return validated

    def _select_candidate_suites(self, config: PipelineConfig) -> list[Path]:
        if config.suites:
            candidates: list[Path] = []
            for suite_path in config.suites:
                path = Path(suite_path)
                if path.is_dir() and "candidates" in path.parts:
                    candidates.append(path.resolve())
            return sorted(candidates)

        tasks = set(config.tasks)
        models = fixed_selection("test-generation model", config.test_models)
        strategies = fixed_selection("strategy", config.test_strategies)
        return sorted(
            path
            for path in candidate_suite_directories(self.validated_tests_root(config))
            if self._matches_suite_selection(
                path,
                config,
                tasks,
                models,
                strategies,
            )
        )

    @staticmethod
    def _matches_suite_selection(
        path: Path,
        config: PipelineConfig,
        tasks: set[str],
        models: set[str],
        strategies: set[str],
    ) -> bool:
        if not path.is_dir():
            return False
        if path.parts[-3] not in models or path.parts[-2] not in strategies:
            return False
        if not config.all_tasks and path.parts[-5] not in tasks:
            return False
        if config.suite_id and path.name != config.suite_id:
            return False
        return True

    def _has_valid_reference_observation(
        self,
        path: Path,
        config: PipelineConfig,
        adapter: LanguageAdapter,
        observations_root: Path,
    ) -> bool:
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
        return bool(
            observation is not None
            and observation.is_technically_executable
            and observation.assertions_passed
        )

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
                Path(path).resolve()
                for path in config.transformations
                if Path(path).is_file()
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
    """Count pairs by what the run established about the transformation.

    Every pair counted here has a reference-validated suite: the selection gate
    in :meth:`TransformationValidationAdapter.select_validated_suites` admits
    only suites whose reference observation was technically executable and whose
    assertions passed. So a failure at this point is a semantic execution
    failure of the pairing, and it is counted as one — Source Diagnosis decides
    afterwards whether the transformation, the test, or neither should change.

    ``evaluated`` (= ``passed`` + ``failed``) is the denominator of semantic
    correctness. ``skipped`` stays outside it for the residual cases where the
    harness could not run this pair at all, so an unobserved pair never becomes
    either a pass or a fail.
    """
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
            # The harness could not run this pair at all: nothing was judged.
            skipped += 1
    return {
        "evaluated": passed + failed,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "infrastructure_errors": infrastructure,
    }
