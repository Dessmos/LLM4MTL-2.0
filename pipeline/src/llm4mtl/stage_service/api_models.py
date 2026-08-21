"""Request/response models for the stage service."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The four languages the thesis must cover. Kept as a closed set so a run can
# never be created for a language the pipeline does not implement.
Language = Literal["etl", "atl", "qvto", "reactions"]


class RunCreateRequest(BaseModel):
    """Identity of a new run. These fields become the immutable manifest.

    A run is exactly one combination, so every axis a stage reads is required.
    Leaving one out would let a stage select every value and attribute the results
    to a run id that does not describe them.

    The four generation axes are nullable because a run mode need not have both
    branches: a semantic-tests-only run has no transformation model, and null on
    that axis is what ``manifest.schema.json`` already means by "not applicable to
    the stages this run executes". Null never means "any value" — a stage needing
    an axis the run left null refuses instead of selecting every value.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str | None = None
    language: Language
    task: str = Field(min_length=1)
    transformation_model: str | None = Field(default=None, min_length=1)
    test_generation_model: str | None = Field(default=None, min_length=1)
    transformation_strategy: str | None = Field(default=None, min_length=1)
    test_generation_strategy: str | None = Field(default=None, min_length=1)
    seed: int = 1
    pipeline_variant: str = "full"
    preset: str | None = None


class RunCreateResponse(BaseModel):
    run_id: str
    status: str = "initialized"


class StageRunRequest(BaseModel):
    """Attempt-specific parameters for one stage.

    Identity belongs only to the immutable run manifest and is deliberately not
    representable here. Rejecting unknown fields makes a stale workflow fail
    loudly instead of appearing to select a different task/model/strategy.
    """

    model_config = ConfigDict(extra="forbid")

    suite_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]+$")
    # Which refinement iteration this attempt belongs to. The run keeps its own
    # copy of the transformation per iteration, and only a *test* refinement
    # renames the suite - so the iteration cannot be read off the suite id
    # without making a transformation refinement look like the initial one.
    refinement_iteration: int | None = Field(default=None, ge=0)
    verbose: bool = False


class RunResultRequest(BaseModel):
    """Where one run's orchestration stopped, and on what budget.

    Only what the workflow itself owns is representable. Stage statuses and the
    diagnosis aggregate are read from the run's own recorded attempts, so a
    stale workflow cannot report a run as passing that its stages recorded as
    failing.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "completed_with_failures", "failed", "incomplete"]
    terminal_state: str = Field(min_length=1, max_length=200)
    run_mode: Literal["full", "tests_only", "transformations_only"]
    refinement_iterations_used: int = Field(ge=0)
    refinement_iterations_allowed: int = Field(ge=0)
    suite_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]+$")


class PromptInputsRequest(BaseModel):
    """Identity of the task whose exact prompt inputs must be resolved."""

    model_config = ConfigDict(extra="forbid")

    language: Language
    task: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")


class DiagnosisRecordRequest(BaseModel):
    """Normalized failure diagnosis returned by an n8n LLM node."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    classification: Literal["TRANSFORMATION_DEFECT", "TEST_DEFECT", "AMBIGUOUS"]
    evidence_ref: str | None = None
    rationale: str = Field(min_length=1)
    provider: Literal["openai", "anthropic", "google"]
    model: str = Field(min_length=1)
    created_at: datetime
