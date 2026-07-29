"""Request/response models for the stage service."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    run_id: str | None = None
    language: str = "etl"
    task: str | None = None
    transformation_model: str | None = None
    test_generation_model: str | None = None
    strategy: str | None = None
    seed: int | None = None
    pipeline_variant: str = "full"
    preset: str | None = None


class RunCreateResponse(BaseModel):
    run_id: str
    status: str = "initialized"


class StageRunRequest(BaseModel):
    """Selection for one stage. n8n owns which stage runs and what comes next."""

    language: str = "etl"
    tasks: list[str] = Field(default_factory=list)
    all_tasks: bool = False
    test_models: list[str] = Field(default_factory=list)
    test_strategies: list[str] = Field(default_factory=list)
    transformation_models: list[str] = Field(default_factory=list)
    transformation_strategies: list[str] = Field(default_factory=list)
    suite_id: str | None = None
    verbose: bool = False


class DiagnosisRecordRequest(BaseModel):
    """Normalized failure diagnosis returned by an n8n LLM node."""

    schema_version: Literal["1.0"]
    classification: Literal["TRANSFORMATION_DEFECT", "TEST_DEFECT", "AMBIGUOUS"]
    evidence_ref: str | None = None
    rationale: str = Field(min_length=1)
    provider: Literal["openai", "anthropic", "google"]
    model: str = Field(min_length=1)
    created_at: datetime
