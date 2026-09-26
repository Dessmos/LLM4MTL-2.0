"""The configuration a stage runs under and the facts it returns.

Both entry points -- the stage service n8n calls and the local runner -- hand a
stage a :class:`PipelineConfig` and record the :class:`StageResult` it returns,
so these types belong to the stages rather than to either caller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Internal stage names: the ``StageResult.name`` each stage reports. The
# contract stage id each one maps to is ``stage_contract.CONTRACT_STAGE_IDS``.
EXTRACTION_STAGE_NAME = "extraction"
TECHNICAL_VALIDATION_STAGE_NAME = "technical_validation"
REFERENCE_VALIDATION_STAGE_NAME = "reference_validation"
TRANSFORMATION_PARSING_STAGE_NAME = "transformation_parsing"
TRANSFORMATION_VALIDATION_STAGE_NAME = "transformation_validation"

# Maven timeout for one suite execution, in every stage that runs a suite.
# Matches the reference-validation CLI default. The stage service has no
# per-request timeout of its own.
SUITE_TIMEOUT_SECONDS = 240



class ConfigError(ValueError):
    """Raised when an experiment configuration violates the run contract."""


@dataclass
class PipelineConfig:
    """Mutable selections and runtime controls for one stage or runner invocation."""

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
    technical_validation: bool = True
    reference_validation: bool = True
    transformation_parsing: bool = True
    semantic_validation: bool = True
    test_validation_stage: str = "all"
    start_stage: str = "extract"
    stop_after: str = "semantic"
    run_id: str | None = None
    # The launch this run belongs to. None means "start a new batch": the run
    # store claims the next free batch directory. Not an identity axis: it says
    # where the run is filed, not what it computes.
    batch_id: str | None = None
    # Identity axes recorded in the immutable manifest alongside language/task/models.
    seed: int = 1
    pipeline_variant: str = "full"
    resume: bool = False
    force: bool = False
    dry_run: bool = False
    output_format: str = "text"
    fail_fast: bool = False
    engine_dir: str | None = None
    # The run directory, resolved by the run store. Not an identity axis: the
    # stages use it to keep their evidence inside the current run.
    run_dir: str | None = None
    transformation_selection_locked: bool = False
    command: str = "pipeline.run"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageResult:
    """Internal stage facts and evidence, translated to the contract by ``stage_contract``."""

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
