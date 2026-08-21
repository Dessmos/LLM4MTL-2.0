"""Run directory layout for the run-centric artifact store.

One run lives under ``artifacts/work/runs/<run-id>/`` and is described by:

* ``manifest.json`` — immutable resolved config + provenance (written once).
* ``events.jsonl`` — append-only timeline.
* ``stages/<stage>/attempts/attempt-NNN/result.json`` — immutable canonical stage
  result (``schemas/stage-result.schema.json``). The "latest" result is derived
  from these on read; there is no mutable projection that could go stale.
* ``stages/<stage>/attempts/attempt-NNN/evidence.json`` — immutable internal
  detail behind that result (commands, stdout, selections). Never a contract.
* ``responses/<operation>/iteration-NNN/`` — run-scoped raw generation output.
* ``responses/<operation>/attempt-NNN/`` — immutable normalized LLM responses.
* ``transformation/iteration-NNN/`` — the run's own copy of the transformations
  it judged, adopted from that run's raw response, with the ``metadata.json``
  that says where each came from.
* ``result.json`` — the terminal result, written once when the run ends.

``<stage>`` is always a contract stage id (see ``llm4mtl.stage_contract``), so a
run directory reads the same whether the local runner or the stage service wrote
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class RunPaths:
    """Filesystem layout of a single run directory."""

    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def events(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def stages_dir(self) -> Path:
        return self.root / "stages"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def metrics_dir(self) -> Path:
        return self.root / "metrics"

    @property
    def responses_dir(self) -> Path:
        return self.root / "responses"

    def stage_dir(self, stage: str) -> Path:
        return self.stages_dir / stage

    def stage_attempts_dir(self, stage: str) -> Path:
        return self.stage_dir(stage) / "attempts"

    def stage_attempt_dir(self, stage: str, attempt: int) -> Path:
        return self.stage_attempts_dir(stage) / f"attempt-{attempt:03d}"

    def stage_attempt_result(self, stage: str, attempt: int) -> Path:
        return self.stage_attempt_dir(stage, attempt) / "result.json"

    def stage_attempt_evidence(self, stage: str, attempt: int) -> Path:
        return self.stage_attempt_dir(stage, attempt) / "evidence.json"

    def response_operation_dir(self, operation: str) -> Path:
        return self.responses_dir / operation

    def response_attempt_dir(self, operation: str, attempt: int) -> Path:
        return self.response_operation_dir(operation) / f"attempt-{attempt:03d}"

    def generation_iteration_dir(self, operation: str, iteration: int) -> Path:
        """Run-scoped raw generation artifacts for one refinement iteration."""
        return self.response_operation_dir(operation) / f"iteration-{iteration:03d}"

    def generation_response(
        self,
        operation: str,
        iteration: int,
        filename: str,
    ) -> Path:
        """The exact raw response a deterministic stage consumes."""
        return self.generation_iteration_dir(operation, iteration) / filename

    def refinement_dir(self, artifact_type: str, iteration: int) -> Path:
        return self.root / "refinements" / artifact_type / f"iteration-{iteration:03d}"

    def generation_record(self, artifact_type: str, iteration: int) -> Path:
        return (
            self.root
            / "generations"
            / artifact_type
            / f"iteration-{iteration:03d}"
            / "generation.json"
        )
