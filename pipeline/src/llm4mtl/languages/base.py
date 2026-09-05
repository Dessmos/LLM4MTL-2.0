"""What the shared pipeline needs from a language, and nothing more.

The pipeline is one orchestration model for all four languages; everything that
differs between them lives behind this boundary. The interface is deliberately
narrow — it covers only capabilities the pipeline actually calls today, so it
stays a real seam rather than a speculative framework.

Explicitly NOT on this interface:

* generating transformations — that is n8n's job and predates this pipeline;
* choosing providers, prompts, or routes — those belong to n8n;
* storing artifacts or deriving metrics — the run store and evaluation layer own
  those, and keeping them out is what lets metrics be reproduced from stored
  observations without re-running any engine;
* mutation operators and reference instrumentation — separate capabilities with
  a different lifecycle, added when the mutation framework lands.
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

        Returns the observation and the raw Maven/Surefire evidence it was
        derived from. The evidence is part of this contract because it can only
        be read inside the execution: the workspace it lives in is wiped by the
        next execution's ``mvn clean``, so a caller that asked for it afterwards
        would find it gone.
        """

    def normalize_transformation_failure(
        self,
        observation: SuiteExecutionObservation,
    ) -> TransformationOutcome | None:
        """Normalize an attributable execution failure into the shared taxonomy.

        ``None`` means the observation is suite/harness-side, or execution
        reached assertions and therefore needs output snapshots rather than a
        fabricated failure outcome.
        """

    def parse_transformations(
        self,
        transformations: Sequence[Path],
        workspace: Workspace,
    ) -> dict[Path, ParseObservation]:
        """Syntax-check generated transformations with this language's parser."""
