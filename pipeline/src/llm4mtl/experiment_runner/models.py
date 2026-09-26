"""Aggregate result of one local runner invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from llm4mtl.stages.models import StageResult


@dataclass
class RunResult:
    """Aggregate result returned by one local runner invocation."""

    run_id: str
    status: str
    command: str
    stages: list[StageResult] = field(default_factory=list)
    run_dir: str | None = None
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "command": self.command,
            "run_dir": self.run_dir,
            "stages": {stage.name: stage.to_dict() for stage in self.stages},
            "summary": self.summary(),
            "error": self.error,
        }

    def summary(self) -> dict[str, Any]:
        return {stage.name: stage.counts for stage in self.stages}
