"""The two validation gates, shared by the stand-alone CLIs and the test stage.

The validation CLIs and :mod:`llm4mtl.stages.test_generation` call these
functions with the same typed context, so technical executability and oracle
validity are defined once.

Suite verdicts are also the funnel's denominators, so they are counted here
too. A suite that could not run was never judged as an oracle, and must count
on neither the passing nor the failing side.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from llm4mtl.domain import GeneratedSuite, SuiteExecutionObservation
from llm4mtl.domain.observations import FailureStage
from llm4mtl.languages.base import LanguageAdapter, Workspace
from llm4mtl.semantic_tests.suite_execution import (
    observation_lock,
    read_observation,
    record_observation,
)

# Per-suite verdicts. ARTIFACT_INVALID and NOT_EXECUTABLE mean the oracle
# question was never asked; only VALIDATED and REFERENCE_INVALID answer it.
ARTIFACT_INVALID = "ARTIFACT_INVALID"
INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
NOT_EXECUTABLE = "NOT_EXECUTABLE"
REFERENCE_INVALID = "REFERENCE_INVALID"
TECHNICALLY_EXECUTABLE = "TECHNICALLY_EXECUTABLE"
VALIDATED = "VALIDATED"


@dataclass(frozen=True)
class ValidationContext:
    """Everything a validation gate needs, resolved once by the caller."""

    adapter: LanguageAdapter
    workspace: Workspace
    timeout: int


@dataclass(frozen=True)
class SuiteVerdict:
    """One suite's outcome at one gate, with the observation behind it."""

    suite: GeneratedSuite
    status: str
    observation: SuiteExecutionObservation | None = None
    error_summary: str = ""

    @property
    def is_technically_executable(self) -> bool:
        return (
            self.observation is not None and self.observation.is_technically_executable
        )

    @property
    def failure_stage(self) -> str:
        if self.observation is not None:
            return self.observation.failure_stage
        if self.status == ARTIFACT_INVALID:
            return FailureStage.ARTIFACT_VALIDATION
        return FailureStage.INFRASTRUCTURE


def observe_suite(suite: GeneratedSuite, context: ValidationContext) -> SuiteVerdict:
    """Execute ``suite`` against its reference once, reusing a recorded run.

    Returns a verdict whose status is the *technical* one; reference validation
    refines the same observation into an oracle verdict.
    """
    validation = context.adapter.validate_suite_artifacts(suite)
    if not validation.valid:
        return SuiteVerdict(
            suite,
            ARTIFACT_INVALID,
            error_summary="; ".join(validation.violations),
        )

    reference = context.adapter.reference_transformation(suite.task)
    if not reference.is_file():
        return SuiteVerdict(
            suite,
            INFRASTRUCTURE_ERROR,
            error_summary=f"Reference transformation not found: {reference}",
        )

    observation = _reference_observation(suite, reference, context)
    return SuiteVerdict(
        suite,
        _technical_status(observation),
        observation=observation,
        error_summary=observation.error_summary,
    )


def _reference_observation(
    suite: GeneratedSuite,
    reference: Path,
    context: ValidationContext,
) -> SuiteExecutionObservation:
    """Return the recorded reference observation, executing once if absent."""
    observations_root = context.workspace.observations_dir
    # Read again while holding the per-suite lock. Without it, the technical and
    # the reference stage could both see no record and run the same harness
    # at the same time.
    with observation_lock(observations_root, suite):
        observation = read_observation(observations_root, suite, reference)
        if observation is None:
            observation, evidence = context.adapter.execute_suite(
                suite, reference, context.workspace, context.timeout
            )
            # Recorded in the same call: the reports behind this observation only
            # exist until the next suite's `mvn clean` runs in this workspace.
            record_observation(
                observations_root, suite, reference, observation, evidence=evidence
            )
    return observation


def judge_oracle(verdict: SuiteVerdict) -> SuiteVerdict:
    """Refine a technical verdict into the oracle verdict for the same execution."""
    if verdict.observation is None or not verdict.observation.is_technically_executable:
        return verdict
    return SuiteVerdict(
        verdict.suite,
        VALIDATED if verdict.observation.assertions_passed else REFERENCE_INVALID,
        observation=verdict.observation,
        error_summary=verdict.error_summary,
    )


def _technical_status(observation: SuiteExecutionObservation) -> str:
    if observation.is_technically_executable:
        return TECHNICALLY_EXECUTABLE
    if observation.is_infrastructure_failure:
        return INFRASTRUCTURE_ERROR
    return NOT_EXECUTABLE


def technical_counts(verdicts: list[SuiteVerdict], selected: int) -> dict[str, int]:
    """Stage counts for technical executability. Assertions are not judged here.

    ``compile_failed`` is separated from the rest because the n8n contract routes
    a compile failure differently from an execution failure.
    """
    tally = Counter(verdict.status for verdict in verdicts)
    compile_failed = sum(
        1
        for verdict in verdicts
        if verdict.status == NOT_EXECUTABLE
        and verdict.failure_stage == FailureStage.JAVA_COMPILATION
    )
    return {
        "selected": selected,
        "passed": tally[TECHNICALLY_EXECUTABLE],
        "failed": tally[NOT_EXECUTABLE],
        "compile_failed": compile_failed,
        "invalid": tally[ARTIFACT_INVALID],
        "infrastructure_errors": tally[INFRASTRUCTURE_ERROR],
        "skipped": max(0, selected - len(verdicts)),
    }


def reference_counts(verdicts: list[SuiteVerdict], selected: int) -> dict[str, int]:
    """Count oracle verdicts without treating unexecutable suites as invalid."""
    tally = Counter(verdict.status for verdict in verdicts)
    unjudged = tally[NOT_EXECUTABLE] + tally[ARTIFACT_INVALID]
    return {
        "selected": selected,
        "validated": tally[VALIDATED],
        "invalid": tally[REFERENCE_INVALID],
        "infrastructure_errors": tally[INFRASTRUCTURE_ERROR],
        "skipped": unjudged + max(0, selected - len(verdicts)),
    }


def workspace_for(engine_dir: Path, observations_dir: Path) -> Workspace:
    """Resolve a validation workspace independently of the process directory."""
    return Workspace(
        engine_dir=engine_dir.resolve(),
        observations_dir=observations_dir.resolve(),
    )
