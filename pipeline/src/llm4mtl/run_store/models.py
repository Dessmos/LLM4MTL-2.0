"""Run directory layout for the run-centric artifact store.

One run lives under ``artifacts/work/runs/<batch-id>/<run-id>/`` — the batch is
the launch that created it (see ``run_store.batches``) — and is described by:

* ``manifest.json`` — immutable resolved config + provenance (written once).
* ``task-prompt.md``, ``metamodel.txt`` — a custom task's inputs, when it has
  them.
* ``events.jsonl`` — append-only timeline.
* ``stages/<stage>/attempts/attempt-NNN/result.json`` — immutable canonical stage
  result (``schemas/stage-result.schema.json``). The "latest" result is derived
  from these on read; there is no mutable projection that could go stale.
* ``stages/<stage>/attempts/attempt-NNN/evidence.json`` — immutable internal
  detail behind that result (commands, stdout, selections). Never a contract.
* ``responses/<operation>/iteration-NNN/`` — run-scoped raw generation output.
* ``generations/<artifact-type>/iteration-NNN/generation.json`` — write-once
  provenance of one generation call.
* ``refinements/<artifact-type>/iteration-NNN/`` — the prepared refinement
  request and prompt.
* ``observations/`` — what the stages observed while executing suites and
  parsers.
* ``workspaces/`` — the run-local engine harnesses those executions used.
* ``transformation/iteration-NNN/`` — the run's own copy of the transformations
  it judged, adopted from that run's raw response, with the ``metadata.json``
  that says where each came from.
* ``result.json`` — the terminal result, written once when the run ends.

``<stage>`` is always a contract stage id (see ``llm4mtl.vocabulary``), so a
run directory reads the same whether the local runner or the stage service wrote
it.

This class knows only the inside of a run. Where the run sits — its batch, its
diagnoses directory, how n8n sees it — is ``llm4mtl.paths.ArtifactRoots``, and
nothing here reads the run's directory name back to derive another location.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.run_store.attempts import attempt_dir_name

SCHEMA_VERSION = "2.0"
# The wall-clock stamp of a write-once record. A retry legitimately moves it,
# so records are compared without it.
RECORDED_AT = "recorded_at"
PROMPT_FILENAME = "prompt.md"
OBSERVATIONS_DIRNAME = "observations"
# The run-local copies of the engine harnesses the stages execute in.
WORKSPACES_DIRNAME = "workspaces"


def iteration_dir_name(iteration: int) -> str:
    """The directory name of one refinement iteration, ``iteration-NNN``."""
    return f"iteration-{iteration:03d}"


def without_recorded_at(record: dict[str, Any]) -> dict[str, Any]:
    """``record`` without its wall-clock stamp."""
    return {key: value for key, value in record.items() if key != RECORDED_AT}


@dataclass(frozen=True)
class RunPaths:
    """Filesystem layout of a single run directory."""

    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def task_prompt(self) -> Path:
        """The custom task prompt this run was created with, when it has one."""
        return self.root / "task-prompt.md"

    @property
    def metamodel(self) -> Path:
        """The custom task metamodel this run was created with, when it has one."""
        return self.root / "metamodel.txt"

    @property
    def events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def stages_dir(self) -> Path:
        return self.root / "stages"

    @property
    def responses_dir(self) -> Path:
        return self.root / "responses"

    @property
    def observations_dir(self) -> Path:
        return self.root / OBSERVATIONS_DIRNAME

    @property
    def workspaces_dir(self) -> Path:
        return self.root / WORKSPACES_DIRNAME

    def stage_dir(self, stage: str) -> Path:
        return self.stages_dir / stage

    def stage_attempts_dir(self, stage: str) -> Path:
        return self.stage_dir(stage) / "attempts"

    def stage_attempt_dir(self, stage: str, attempt: int) -> Path:
        return self.stage_attempts_dir(stage) / attempt_dir_name(attempt)

    def stage_attempt_result(self, stage: str, attempt: int) -> Path:
        return self.stage_attempt_dir(stage, attempt) / "result.json"

    def stage_attempt_evidence(self, stage: str, attempt: int) -> Path:
        return self.stage_attempt_dir(stage, attempt) / "evidence.json"

    def response_operation_dir(self, operation: str) -> Path:
        return self.responses_dir / operation

    def generation_iteration_dir(self, operation: str, iteration: int) -> Path:
        """Run-scoped raw generation artifacts for one refinement iteration."""
        return self.response_operation_dir(operation) / iteration_dir_name(iteration)

    def generation_response(
        self,
        operation: str,
        iteration: int,
        filename: str,
    ) -> Path:
        """The exact raw response a deterministic stage consumes."""
        return self.generation_iteration_dir(operation, iteration) / filename

    def generation_prompt(self, operation: str, iteration: int) -> Path:
        """The fully assembled prompt a generation workflow archived, if any."""
        return self.generation_iteration_dir(operation, iteration) / PROMPT_FILENAME

    def refinement_dir(self, artifact_type: str, iteration: int) -> Path:
        return self.root / "refinements" / artifact_type / iteration_dir_name(iteration)

    def refinement_request(self, artifact_type: str, iteration: int) -> Path:
        return self.refinement_dir(artifact_type, iteration) / "request.json"

    def refinement_prompt(self, artifact_type: str, iteration: int) -> Path:
        return self.refinement_dir(artifact_type, iteration) / PROMPT_FILENAME

    def generation_record(self, artifact_type: str, iteration: int) -> Path:
        return (
            self.root
            / "generations"
            / artifact_type
            / iteration_dir_name(iteration)
            / "generation.json"
        )
