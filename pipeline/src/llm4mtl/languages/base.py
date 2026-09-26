"""What the shared pipeline needs from a language, and nothing more.

The pipeline runs all four languages the same way; everything that differs
between them lives behind this interface. It holds only the methods the pipeline
calls today.

Not on this interface:

* generating transformations, and choosing providers, prompts, or routes —
  n8n owns those;
* storing artifacts or computing metrics — the run store and evaluation layer
  own those, so metrics can be recomputed from stored observations without
  running an engine again;
* mutation operators and reference instrumentation — not built yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence, runtime_checkable

from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    RawExecutionEvidence,
    SuiteExecutionObservation,
    TransformationOutcome,
)


@dataclass(frozen=True)
class Workspace:
    """The materialized engine directory one stage attempt executes in."""

    engine_dir: Path
    observations_dir: Path


@runtime_checkable
class LanguageAdapter(Protocol):
    """One language's parser, harness, and execution conventions."""

    language_id: str
    renderer_version: str

    def runtime_tool_versions(self) -> dict[str, str]:
        """Language-engine versions that must be pinned in run provenance."""

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        """Validate the structured spec and render this language's harness."""

    def reference_transformation(self, task: str) -> Path:
        """The trusted reference transformation for ``task``."""

    def validate_suite_artifacts(self, suite: GeneratedSuite) -> ArtifactValidation:
        """Whether ``suite`` is a usable artifact, without executing anything."""

    def execute_suite(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        workspace: Workspace,
        timeout: int,
    ) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
        """Run ``suite`` against ``transformation`` and report the observed facts.

        Returns the observation and the raw Maven/Surefire evidence behind it.
        The evidence must be read during the execution: the next execution's
        ``mvn clean`` wipes the workspace it lives in.
        """

    def normalize_transformation_failure(
        self,
        observation: SuiteExecutionObservation,
    ) -> TransformationOutcome | None:
        """Normalize an attributable execution failure into the shared taxonomy.

        Returns ``None`` when the failure is on the suite or harness side, or
        when execution reached the assertions. Those cases are judged from the
        output snapshots, not from an invented failure outcome.
        """

    def parse_transformations(
        self,
        transformations: Sequence[Path],
        workspace: Workspace,
    ) -> dict[Path, ParseObservation]:
        """Syntax-check generated transformations with this language's parser."""
