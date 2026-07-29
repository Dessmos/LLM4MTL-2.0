"""The two validation gates, shared by the CLI and the orchestrator.

Both entry points call these functions with the same typed context, so there is
one implementation of what technical executability and oracle validity mean. The
orchestrator previously re-derived those verdicts by running the CLI and matching
its printed output with regular expressions — two implementations of one rule,
and the fragile one decided the experiment's counts.

Suite verdicts are also the funnel's denominators, which is why counting them is
here rather than at a caller: a suite that could not be executed was never judged
as an oracle, and must not be added to either the passing or the failing side.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from llm4mtl.domain import GeneratedSuite, SuiteExecutionObservation
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

JUDGED_STATUSES = frozenset({VALIDATED, REFERENCE_INVALID})


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
        return self.observation is not None and self.observation.is_technically_executable

    @property
    def is_judged_as_oracle(self) -> bool:
        return self.status in JUDGED_STATUSES

    @property
    def failure_stage(self) -> str:
        if self.observation is not None:
            return self.observation.failure_stage
        return "artifact_validation" if self.status == ARTIFACT_INVALID else "infrastructure"


def observe_suite(suite: GeneratedSuite, context: ValidationContext) -> SuiteVerdict:
    """Execute ``suite`` against its reference once, reusing a recorded run.

    Returns a verdict whose status is the *technical* one; reference validation
    refines the same observation into an oracle verdict.
    """
    validation = context.adapter.validate_suite_artifacts(suite)
    if not validation.valid:
        return SuiteVerdict(suite, ARTIFACT_INVALID, error_summary="; ".join(validation.violations))

    reference = context.adapter.reference_transformation(suite.task)
    if not reference.is_file():
        return SuiteVerdict(
            suite,
            INFRASTRUCTURE_ERROR,
            error_summary=f"Reference transformation not found: {reference}",
        )

    observations_root = context.workspace.observations_dir
    # The second read happens while holding the per-suite lock. Without it,
    # technical and reference stage calls can both observe a miss and execute
    # the same mutable harness concurrently.
    with observation_lock(observations_root, suite):
        observation = read_observation(observations_root, suite, reference)
        if observation is None:
            observation = context.adapter.execute_suite(
                suite, reference, context.workspace, context.timeout
            )
            record_observation(observations_root, suite, reference, observation)

    return SuiteVerdict(
        suite,
        _technical_status(observation),
        observation=observation,
        error_summary=observation.error_summary,
    )


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
    return INFRASTRUCTURE_ERROR if observation.is_infrastructure_failure else NOT_EXECUTABLE


def technical_counts(verdicts: list[SuiteVerdict], selected: int) -> dict[str, int]:
    """Stage counts for technical executability. Assertions are not judged here.

    ``compile_failed`` is separated from the rest because the n8n contract routes
    a compile failure differently from an execution failure.
    """
    tally = Counter(verdict.status for verdict in verdicts)
    compile_failed = sum(
        1
        for verdict in verdicts
        if verdict.status == NOT_EXECUTABLE and verdict.failure_stage == "java_compilation"
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
    """Stage counts for oracle validity. Unexecutable suites are unjudged, not invalid."""
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
    return Workspace(engine_dir=engine_dir.resolve(), observations_dir=observations_dir.resolve())
