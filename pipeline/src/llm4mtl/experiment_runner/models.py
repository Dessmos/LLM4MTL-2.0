"""Configuration and result models for the experiment runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PipelineConfig:
    # Language is an experiment identity axis, not a shared-pipeline default.
    # Every boundary must state it explicitly so a missing value cannot silently
    # execute ETL and be attributed to another language.
    language: str
    tasks: list[str] = field(default_factory=list)
    all_tasks: bool = False
    responses: list[str] = field(default_factory=list)
    suites: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    test_models: list[str] = field(default_factory=list)
    test_strategies: list[str] = field(default_factory=list)
    transformation_models: list[str] = field(default_factory=list)
    transformation_strategies: list[str] = field(default_factory=list)
    suite_id: str | None = None
    overwrite: bool = False
    technical_validation: bool = True
    reference_validation: bool = True
    transformation_parsing: bool = True
    semantic_validation: bool = True
    test_validation_stage: str = "all"
    start_stage: str = "extract"
    stop_after: str = "semantic"
    run_id: str | None = None
    # Identity axes recorded in the immutable manifest alongside language/task/models.
    seed: int = 1
    pipeline_variant: str = "full"
    resume: bool = False
    force: bool = False
    dry_run: bool = False
    output_format: str = "text"
    verbose: bool = False
    keep_workspace: bool = False
    fail_fast: bool = False
    engine_dir: str | None = None
    # Runtime scope resolved by the run store. This is deliberately not an
    # experiment identity axis; adapters use it to keep evidence inside the
    # current run even when the orchestrator has a non-default runs root.
    run_dir: str | None = None
    transformation_selection_locked: bool = False
    command: str = "pipeline.run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageResult:
    name: str
    status: str
    counts: dict[str, int] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    input_hash: str = ""
    config_hash: str = ""
    exit_code: int = 0

    @property
    def domain_failures(self) -> int:
        return sum(
            self.counts.get(key, 0)
            for key in ("failed", "invalid", "infrastructure_errors")
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StageResult":
        return cls(**payload)


@dataclass
class RunResult:
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
