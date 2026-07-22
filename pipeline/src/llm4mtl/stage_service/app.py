"""FastAPI stage service. Transport only — the pipeline does the work."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from llm4mtl import run_store
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator, generate_run_id
from llm4mtl.paths import TARGET
from llm4mtl.stage_contract import STAGE_DISPATCH, to_stage_payload
from llm4mtl.stage_service.api_models import (
    RunCreateRequest,
    RunCreateResponse,
    StageRunRequest,
)

app = FastAPI(title="LLM4MTL stage service", version="0.1.0")
_orchestrator = ExperimentOrchestrator()


def _runs_root():
    return TARGET.runs


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs", response_model=RunCreateResponse)
def create_run(request: RunCreateRequest) -> RunCreateResponse:
    run_id = request.run_id or generate_run_id(
        PipelineConfig(language=request.language, tasks=[request.task] if request.task else [])
    )
    try:
        run_store.create_run(
            _runs_root(),
            run_id,
            {
                "language": request.language,
                "task": request.task,
                "transformation_model": request.transformation_model,
                "test_generation_model": request.test_generation_model,
                "strategy": request.strategy,
                "seed": request.seed,
                "pipeline_variant": request.pipeline_variant,
                "preset": request.preset,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except run_store.ManifestExistsError as exc:
        raise HTTPException(status_code=409, detail=f"run already exists: {run_id}") from exc
    return RunCreateResponse(run_id=run_id)


@app.post("/runs/{run_id}/stages/{stage}")
def run_stage(run_id: str, stage: str, request: StageRunRequest) -> dict[str, Any]:
    if stage not in STAGE_DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage}")
    paths = run_store.open_run(_runs_root(), run_id)
    if not paths.manifest.exists():
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")

    config = PipelineConfig(
        language=request.language,
        tasks=list(request.tasks),
        all_tasks=request.all_tasks,
        test_models=list(request.test_models),
        test_strategies=list(request.test_strategies),
        transformation_models=list(request.transformation_models),
        transformation_strategies=list(request.transformation_strategies),
        suite_id=request.suite_id,
        verbose=request.verbose,
        run_id=run_id,
    )
    adapter_attr, method_name = STAGE_DISPATCH[stage]
    adapter = getattr(_orchestrator, adapter_attr)

    run_store.append_event(paths, "stage_started", stage=stage)
    try:
        result = getattr(adapter, method_name)(config, False)
    except Exception as exc:
        result = StageResult(
            stage,
            "infrastructure_error",
            {"infrastructure_errors": 1},
            {"error": f"{type(exc).__name__}: {exc}"},
            exit_code=1,
        )
    payload = to_stage_payload(stage, result)
    attempt = run_store.record_attempt(paths, stage, payload)
    payload["attempt"] = attempt
    run_store.append_event(
        paths,
        "stage_finished",
        stage=stage,
        status=payload["status"],
        outcome_code=payload["outcome_code"],
        attempt=attempt,
    )
    return payload


@app.get("/runs/{run_id}/stages/{stage}")
def get_stage(run_id: str, stage: str) -> dict[str, Any]:
    paths = run_store.open_run(_runs_root(), run_id)
    latest = run_store.read_latest(paths, stage)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"no result for stage {stage}")
    return latest


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    paths = run_store.open_run(_runs_root(), run_id)
    manifest = run_store.read_manifest(paths)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    return {"run_id": run_id, "manifest": manifest, "stages": run_store.list_stages(paths)}
