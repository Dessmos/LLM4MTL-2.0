"""FastAPI stage service. Transport only — the pipeline does the work."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from llm4mtl import run_store
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator, generate_run_id
from llm4mtl.paths import TARGET
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
    resolve_task_inputs,
)
from llm4mtl.provenance import ProvenanceError, build_provenance
from llm4mtl.run_store.identity import InvalidRunIdError
from llm4mtl.stage_contract import STAGE_DISPATCH, to_stage_payload
from llm4mtl.stage_service.api_models import (
    DiagnosisRecordRequest,
    PromptInputsRequest,
    RunCreateRequest,
    RunCreateResponse,
    StageRunRequest,
)

app = FastAPI(title="LLM4MTL stage service", version="0.1.0")
_orchestrator = ExperimentOrchestrator()


def _runs_root():
    return TARGET.runs


def _open_run(run_id: str) -> run_store.RunPaths:
    """Open a run, translating a malformed or escaping id into a 400."""
    try:
        return run_store.open_run(_runs_root(), run_id)
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_manifest(run_id: str) -> tuple[run_store.RunPaths, dict[str, Any]]:
    paths = _open_run(run_id)
    manifest = run_store.read_manifest(paths)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    return paths, manifest


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/prompt-inputs/resolve")
def resolve_prompt_inputs(request: PromptInputsRequest) -> dict[str, Any]:
    """Return only the exact LLM inputs selected by the task contract."""
    try:
        return resolve_task_inputs(request.language, request.task).to_dict()
    except TaskInputResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/runs", response_model=RunCreateResponse)
def create_run(request: RunCreateRequest) -> RunCreateResponse:
    if request.task == "all":
        raise HTTPException(
            status_code=422,
            detail="a run must fix one concrete task; expand all tasks through a matrix",
        )
    run_id = request.run_id or generate_run_id(
        PipelineConfig(language=request.language, tasks=[request.task])
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
                "transformation_strategy": request.transformation_strategy,
                "test_generation_strategy": request.test_generation_strategy,
                "seed": request.seed,
                "pipeline_variant": request.pipeline_variant,
                "preset": request.preset,
                "provenance": build_provenance(request.language, request.task),
            },
        )
    except run_store.ManifestExistsError as exc:
        raise HTTPException(status_code=409, detail=f"run already exists: {run_id}") from exc
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProvenanceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RunCreateResponse(run_id=run_id)


def _stage_config(run_id: str, manifest: dict[str, Any], request: StageRunRequest) -> PipelineConfig:
    """Build stage selection exclusively from the immutable manifest."""
    language = manifest.get("language")
    if not isinstance(language, str) or not language:
        raise HTTPException(status_code=409, detail="run manifest has no language identity")
    task = manifest.get("task")
    if not isinstance(task, str) or not task:
        raise HTTPException(status_code=409, detail="run manifest has no task identity")

    return PipelineConfig(
        language=language,
        tasks=[task],
        test_models=_selection(manifest.get("test_generation_model")),
        test_strategies=_selection(manifest.get("test_generation_strategy")),
        transformation_models=_selection(manifest.get("transformation_model")),
        transformation_strategies=_selection(manifest.get("transformation_strategy")),
        seed=int(manifest.get("seed", 1) or 1),
        pipeline_variant=str(manifest.get("pipeline_variant") or "full"),
        suite_id=request.suite_id,
        verbose=request.verbose,
        run_id=run_id,
    )


def _selection(manifest_value: Any) -> list[str]:
    """The run's own value for a selection axis; null means not applicable."""
    if manifest_value:
        return [str(manifest_value)]
    return []


@app.post("/runs/{run_id}/stages/{stage}")
def run_stage(run_id: str, stage: str, request: StageRunRequest) -> dict[str, Any]:
    if stage not in STAGE_DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage}")
    paths, manifest = _require_manifest(run_id)
    config = _stage_config(run_id, manifest, request)
    config.run_dir = str(paths.root)

    adapter_attr, method_name = STAGE_DISPATCH[stage]
    adapter = getattr(_orchestrator, adapter_attr)
    if stage in {"technical-validation", "reference-validation", "execution"}:
        config.engine_dir = str(
            _orchestrator.prepare_workspace(paths.root, config.language)
        )

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
    attempt = run_store.record_attempt(paths, stage, payload, evidence=result.to_dict())
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
    paths = _open_run(run_id)
    latest = run_store.read_latest(paths, stage)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"no result for stage {stage}")
    return latest


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    paths, manifest = _require_manifest(run_id)
    return {"run_id": run_id, "manifest": manifest, "stages": run_store.list_stages(paths)}


@app.post("/runs/{run_id}/diagnoses")
def record_diagnosis(run_id: str, request: DiagnosisRecordRequest) -> dict[str, Any]:
    """Persist the normalized n8n diagnosis through Python's artifact layer."""
    paths, _ = _require_manifest(run_id)

    diagnosis = request.model_dump(mode="json", exclude_none=True)
    attempt, artifact = run_store.record_diagnosis(paths, diagnosis)
    run_store.append_event(
        paths,
        "diagnosis_recorded",
        stage="diagnosis",
        outcome_code=request.classification,
        attempt=attempt,
    )
    return {**diagnosis, "attempt": attempt, "artifact": artifact}
