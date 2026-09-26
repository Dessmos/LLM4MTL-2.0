"""Execution of validated suites against generated transformations.

This stage asks a different question from reference validation. There the
transformation is trusted, so anything the engine rejects is a broken test.
Here the transformation is under test, so an engine that refuses it is
evidence about the transformation. A suite-side problem (nothing compiled, no
model loaded) still means the transformation was never judged. Reading the same
observation differently per role keeps the two populations apart.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from llm4mtl.conventions import (
    default_generated_tests_root,
    language_config,
)
from llm4mtl.domain import (
    GeneratedSuite,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.domain.observations import FailureStage
from llm4mtl.languages import LanguageAdapter, language_adapter
from llm4mtl.run_store.models import RunPaths
from llm4mtl.semantic_tests.suite_execution import (
    GENERATED_TRANSFORMATION_ROLE,
    observation_lock,
    observation_path,
    read_observation,
    record_observation,
)
from llm4mtl.semantic_tests.suites.discovery import (
    candidate_identity,
    suite_from_path,
)
from llm4mtl.semantic_tests.validation import workspace_for
from llm4mtl.serialization.hashing import file_sha256
from llm4mtl.stages.models import (
    SUITE_TIMEOUT_SECONDS,
    TRANSFORMATION_VALIDATION_STAGE_NAME,
    ConfigError,
    PipelineConfig,
    StageResult,
)
from llm4mtl.stages.selection import (
    existing_files,
    fixed_selection,
    hash_paths,
    select_candidate_suites,
    select_generated_files,
)

def _matching_execution_pairs(
    suites: list[Path],
    transformations: list[Path],
) -> list[tuple[Path, Path]]:
    return [
        (suite, transformation)
        for suite in suites
        for transformation in transformations
        if candidate_identity(suite).task == transformation.stem
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

    def semantic_validation(self, config: PipelineConfig) -> StageResult:
        suites = self.select_validated_suites(config)
        transformations = self.select_transformations(config)
        pairs = _matching_execution_pairs(suites, transformations)
        input_hash = hash_paths(suites + transformations)
        details = _selection_details(suites, transformations)
        counts = {
            "selected_suites": len(suites),
            "selected_transformations": len(transformations),
            "execution_pairs": len(pairs),
        }
        if not pairs:
            counts["failed"] = 1
            return _stage_result("error", counts, details, input_hash)

        observed_pairs = self._execute_pairs(config, pairs)
        counts.update(
            execution_counts(
                (pair.observation, pair.failure_outcome) for pair in observed_pairs
            )
        )
        details["pairs"] = [pair.to_detail() for pair in observed_pairs]
        return _stage_result("completed", counts, details, input_hash)

    def _execute_pairs(
        self,
        config: PipelineConfig,
        pairs: list[tuple[Path, Path]],
    ) -> list[_ObservedExecutionPair]:
        if not config.engine_dir:
            raise ConfigError(
                "transformation execution requires a run-local engine workspace"
            )
        executor = _PairExecutor(
            adapter=language_adapter(config.language),
            language=config.language,
            engine_dir=Path(config.engine_dir),
            observations_root=self._observations_root(config),
        )
        return [
            executor.observe(suite_path, transformation)
            for suite_path, transformation in pairs
        ]

    def select_validated_suites(self, config: PipelineConfig) -> list[Path]:
        """Suites reference-validated by this run, never by a copied directory."""
        candidates = self._select_candidate_suites(config)
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
        return select_candidate_suites(config, self.validated_tests_root(config))

    def _has_valid_reference_observation(
        self,
        path: Path,
        config: PipelineConfig,
        adapter: LanguageAdapter,
        observations_root: Path,
    ) -> bool:
        suite = suite_from_path(path, config.language)
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
        return RunPaths(Path(config.run_dir).resolve()).observations_dir

    def select_transformations(self, config: PipelineConfig) -> list[Path]:
        if config.transformations:
            return existing_files(config.transformations)
        models = fixed_selection("transformation model", config.transformation_models)
        strategies = fixed_selection("strategy", config.transformation_strategies)
        return select_generated_files(
            self.transformations_root(config),
            language_config(config.language).language_key,
            config,
            models=models,
            strategies=strategies,
        )


@dataclass(frozen=True)
class _PairExecutor:
    """Runs the suite/transformation pairs of one execution stage."""

    adapter: LanguageAdapter
    language: str
    engine_dir: Path
    observations_root: Path

    def observe(self, suite_path: Path, transformation: Path) -> _ObservedExecutionPair:
        """Observe one pair, reusing an observation this run already recorded."""
        suite = suite_from_path(suite_path, self.language)
        # Keyed by content, so the same bytes share one observation.
        pair_root = (
            self.observations_root
            / "generated_transformations"
            / file_sha256(transformation)
        )
        with observation_lock(pair_root, suite):
            observation, evidence_path = self._read_or_execute(
                suite, transformation, pair_root
            )
        return _ObservedExecutionPair(
            suite_path=suite_path,
            transformation=transformation,
            observation=observation,
            failure_outcome=self.adapter.normalize_transformation_failure(observation),
            evidence_path=evidence_path,
        )

    def _read_or_execute(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        pair_root: Path,
    ) -> tuple[SuiteExecutionObservation, Path]:
        """The pair's observation and evidence path. The caller holds the pair lock."""
        observation = read_observation(
            pair_root,
            suite,
            transformation,
            transformation_role=GENERATED_TRANSFORMATION_ROLE,
        )
        if observation is not None:
            return observation, observation_path(pair_root, suite)
        workspace = workspace_for(self.engine_dir, pair_root)
        observation, raw_evidence = self.adapter.execute_suite(
            suite,
            transformation,
            workspace,
            SUITE_TIMEOUT_SECONDS,
        )
        # Archived here, inside the per-pair lock: pair N+1 runs `mvn clean` in
        # the same workspace and deletes the reports that explain pair N.
        evidence_path = record_observation(
            pair_root,
            suite,
            transformation,
            observation,
            transformation_role=GENERATED_TRANSFORMATION_ROLE,
            evidence=raw_evidence,
        )
        return observation, evidence_path


def _selection_details(
    suites: list[Path],
    transformations: list[Path],
) -> dict[str, object]:
    """What the stage selected."""
    return {
        "reference_validated_suites": [str(path) for path in suites],
        "transformations": [str(path) for path in transformations],
    }


def _stage_result(
    status: str,
    counts: dict[str, int],
    details: dict[str, object],
    input_hash: str,
) -> StageResult:
    return StageResult(
        TRANSFORMATION_VALIDATION_STAGE_NAME, status, counts, details, input_hash
    )


def execution_counts(
    observations: Iterable[
        tuple[SuiteExecutionObservation, TransformationOutcome | None]
    ],
) -> dict[str, int]:
    """Count pairs by what the run established about the transformation.

    Every pair counted here has a reference-validated suite:
    :meth:`TransformationValidationAdapter.select_validated_suites` admits only
    suites whose reference observation was technically executable and whose
    assertions passed. So a failure here is counted as a semantic execution
    failure of the pair; Source Diagnosis decides later whether the
    transformation, the test, or neither should change.

    ``evaluated`` (= ``passed`` + ``failed``) is the denominator of semantic
    correctness. ``skipped`` stays outside it: the harness could not run the
    pair at all, so an unobserved pair never counts as a pass or a fail.
    """
    categories = Counter(
        _execution_category(observation, failure_outcome)
        for observation, failure_outcome in observations
    )
    passed = categories["passed"]
    failed = categories["failed"]
    return {
        "evaluated": passed + failed,
        "passed": passed,
        "failed": failed,
        "skipped": categories["skipped"],
        "infrastructure_errors": categories["infrastructure_errors"],
    }


def _execution_category(
    observation: SuiteExecutionObservation,
    failure_outcome: TransformationOutcome | None,
) -> str:
    """The count one pair belongs to."""
    if (
        failure_outcome is not None
        and not failure_outcome.status.is_attributable_to_the_transformation
    ):
        # A timeout or an infrastructure failure: the run could not observe it.
        return "infrastructure_errors"
    if observation.assertions_passed:
        return "passed"
    if observation.failure_stage == FailureStage.ASSERTION_FAILURE:
        return "failed"
    if failure_outcome is not None:
        # Any other normalized failure is an observation of the transformation.
        return "failed"
    # The harness could not run this pair at all: nothing was judged.
    return "skipped"
