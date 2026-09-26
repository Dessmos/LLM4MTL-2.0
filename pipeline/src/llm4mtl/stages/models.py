"""The configuration a stage runs under and the facts it returns.

The stage service builds a :class:`PipelineConfig` from the run's manifest,
hands it to a stage, and records the :class:`StageResult` the stage returns.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Internal stage names: the ``StageResult.name`` each stage reports. Persisted
# results use the contract stage id instead (``llm4mtl.vocabulary``).
EXTRACTION_STAGE_NAME = "extraction"
TECHNICAL_VALIDATION_STAGE_NAME = "technical_validation"
REFERENCE_VALIDATION_STAGE_NAME = "reference_validation"
TRANSFORMATION_PARSING_STAGE_NAME = "transformation_parsing"
TRANSFORMATION_VALIDATION_STAGE_NAME = "transformation_validation"

# Maven timeout for one suite execution, in every stage that runs a suite.
# The stage service has no per-request timeout of its own.
SUITE_TIMEOUT_SECONDS = 240



class ConfigError(ValueError):
    """Raised when an experiment configuration violates the run contract."""


@dataclass
class PipelineConfig:
    """What one stage invocation works on, and where it keeps its evidence."""

    # Language is an experiment identity axis, not a shared-pipeline default.
    # Every boundary must state it explicitly so a missing value cannot silently
    # execute ETL and be attributed to another language.
    language: str
    tasks: list[str] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    test_models: list[str] = field(default_factory=list)
    test_strategies: list[str] = field(default_factory=list)
    transformation_models: list[str] = field(default_factory=list)
    transformation_strategies: list[str] = field(default_factory=list)
    suite_id: str | None = None
    # The run-local copy of the language's engine, for stages that run Maven.
    engine_dir: str | None = None
    # The run directory, resolved by the run store. Not an identity axis: the
    # stages use it to keep their evidence inside the current run.
    run_dir: str | None = None


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
