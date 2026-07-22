"""Request/response models for the stage service."""

from __future__ import annotations

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
