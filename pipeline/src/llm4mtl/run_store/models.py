"""Run directory layout for the run-centric artifact store.

One run lives under ``artifacts/work/runs/<run-id>/`` and is described by:

* ``manifest.json`` — immutable resolved config + provenance (written once).
* ``events.jsonl`` — append-only timeline.
* ``stages/<stage>/latest.json`` — mutable projection of the newest attempt.
* ``stages/<stage>/attempts/attempt-NNN/result.json`` — immutable per-attempt evidence.
* ``responses/<operation>/attempt-NNN/`` — immutable normalized LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "1.0"


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

    def stage_latest(self, stage: str) -> Path:
        return self.stage_dir(stage) / "latest.json"

    def stage_attempts_dir(self, stage: str) -> Path:
        return self.stage_dir(stage) / "attempts"

    def stage_attempt_dir(self, stage: str, attempt: int) -> Path:
        return self.stage_attempts_dir(stage) / f"attempt-{attempt:03d}"

    def stage_attempt_result(self, stage: str, attempt: int) -> Path:
        return self.stage_attempt_dir(stage, attempt) / "result.json"

    def response_operation_dir(self, operation: str) -> Path:
        return self.responses_dir / operation

    def response_attempt_dir(self, operation: str, attempt: int) -> Path:
        return self.response_operation_dir(operation) / f"attempt-{attempt:03d}"

    def diagnosis_response(self, attempt: int) -> Path:
        return self.response_attempt_dir("failure-diagnosis", attempt) / "diagnosis.json"
