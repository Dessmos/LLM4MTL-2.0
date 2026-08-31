"""FastAPI stage service. Transport only — the pipeline does the work."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from llm4mtl import run_store
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator, generate_run_id
from llm4mtl.languages import language_adapter
from llm4mtl.paths import TARGET
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
    resolve_task_inputs,
)
from llm4mtl.provenance import ProvenanceError, build_provenance
from llm4mtl.run_store.identity import InvalidRunIdError
from llm4mtl.run_store.transformations import (
    TransformationAdoptionError,
    adopt_transformations,
    adopted_transformations,
    iteration_from_suite_id,
)
from llm4mtl.semantic_tests.diagnosis_preparation import (
    DiagnosisPreparationError,
    diagnosis_artifact_references,
    read_diagnosis_queue,
)
from llm4mtl.stage_contract import STAGE_DISPATCH
from llm4mtl.stage_recording import (
    announce_stage_start,
    infrastructure_error_result,
    record_stage_attempt,
)
from llm4mtl.stage_service.api_models import (
    DiagnosisRecordRequest,
    GenerationRecordRequest,
    PromptInputsRequest,
    RefinementPrepareRequest,
    RunCreateRequest,
    RunCreateResponse,
    RunResultRequest,
    StageRunRequest,
)

app = FastAPI(title="LLM4MTL stage service", version="0.1.0")
_orchestrator = ExperimentOrchestrator()

BAD_REQUEST_RESPONSE = {"description": "Malformed or escaping identifier"}
NOT_FOUND_RESPONSE = {"description": "Requested run, stage, or result not found"}
CONFLICT_RESPONSE = {"description": "Run state conflicts with the request"}
UNPROCESSABLE_RESPONSE = {"description": "Request violates a task or run contract"}
# The stages that judge a generated transformation both read the immutable copy
# adopted from this run's raw generation response.
TRANSFORMATION_STAGES = frozenset({"syntax-validation", "execution"})


def _runs_root():
    return TARGET.runs


def _diagnoses_root():
    return TARGET.diagnoses


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


@app.post(
    "/prompt-inputs/resolve",
    responses={422: UNPROCESSABLE_RESPONSE},
)
def resolve_prompt_inputs(request: PromptInputsRequest) -> dict[str, Any]:
    """Return only the exact LLM inputs selected by the task contract."""
    try:
        return resolve_task_inputs(request.language, request.task).to_dict()
    except TaskInputResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/runs",
    response_model=RunCreateResponse,
    responses={
        400: BAD_REQUEST_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: UNPROCESSABLE_RESPONSE,
    },
)
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
        manifest = {
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
        }
        if request.experiment_config is not None:
            manifest["experiment_config"] = request.experiment_config.model_dump()
        run_store.create_run(
            _runs_root(),
            run_id,
            manifest,
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


def _run_transformations(
    paths: run_store.RunPaths,
    manifest: dict[str, Any],
    config: PipelineConfig,
    request: StageRunRequest,
):
    """The run's immutable copy of the transformations this iteration judges.

    Adopted once from the run-scoped raw response by whichever stage of the
    artifact iteration runs first. Every later stage reads the copy back.
    """
    # Stated by the caller when it knows it; otherwise read from the suite id,
    # which encodes it for every run whose tests were the refined artefact.
    iteration = (
        request.refinement_iteration
        if request.refinement_iteration is not None
        else iteration_from_suite_id(request.suite_id)
    )
    existing = adopted_transformations(paths, iteration)
    if existing is not None:
        return existing
    extension = language_adapter(config.language).reference_transformation(
        config.tasks[0]
    ).suffix
    response = paths.generation_response(
        "transformation-generation",
        iteration,
        f"{config.tasks[0]}{extension}",
    )
    if not response.is_file() and request.refinement_iteration is not None:
        raise TransformationAdoptionError(
            f"run-scoped generated transformation is missing: {response}"
        )
    sources = [response] if response.is_file() else []
    return adopt_transformations(paths, manifest, sources, iteration=iteration)


def _generation_artifact_references(
    paths: run_store.RunPaths, stage: str, request: StageRunRequest
) -> dict[str, str]:
    """Generation records responsible for the artifact iteration this stage judged."""
    references: dict[str, str] = {}
    if stage in {"extract", "technical-validation", "reference-validation"}:
        test_iteration = request.refinement_iteration or 0
        _add_generation_reference(
            paths,
            references,
            "semantic_test_generation_record",
            "semantic-test",
            test_iteration,
        )
    if stage in {"syntax-validation", "execution"}:
        transformation_iteration = (
            request.refinement_iteration
            if request.refinement_iteration is not None
            else iteration_from_suite_id(request.suite_id)
        )
        _add_generation_reference(
            paths,
            references,
            "transformation_generation_record",
            "transformation",
            transformation_iteration,
        )
    if stage == "execution":
        _add_generation_reference(
            paths,
            references,
            "semantic_test_generation_record",
            "semantic-test",
            iteration_from_suite_id(request.suite_id),
        )
    return references


def _add_generation_reference(
    paths: run_store.RunPaths,
    references: dict[str, str],
    key: str,
    artifact_type: str,
    iteration: int,
) -> None:
    generation = paths.generation_record(artifact_type, iteration)
    if generation.is_file():
        references[key] = generation.relative_to(paths.root).as_posix()


@app.post(
    "/runs/{run_id}/stages/{stage}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def run_stage(run_id: str, stage: str, request: StageRunRequest) -> dict[str, Any]:
    if stage not in STAGE_DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage}")
    paths, manifest = _require_manifest(run_id)
    config = _stage_config(run_id, manifest, request)
    config.run_dir = str(paths.root)

    if stage == "extract":
        iteration = request.refinement_iteration or 0
        config.responses = [
            str(
                paths.generation_response(
                    "semantic-test-generation",
                    iteration,
                    f"{config.tasks[0]}.md",
                )
            )
        ]

    if stage in TRANSFORMATION_STAGES:
        try:
            adopted = _run_transformations(paths, manifest, config, request)
        except TransformationAdoptionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if adopted is not None:
            # Both stages judge the same bytes for the whole iteration: without
            # this, execution re-selects from the shared tree and can validate a
            # file the parser never saw.
            config.transformations = [str(path) for path in adopted.paths]

    adapter_attr, method_name = STAGE_DISPATCH[stage]
    adapter = getattr(_orchestrator, adapter_attr)
    if stage in {"technical-validation", "reference-validation", "execution"}:
        config.engine_dir = str(
            _orchestrator.prepare_workspace(paths.root, config.language)
        )

    # Announced before the work, so a stage that dies mid-execution leaves a
    # started event with no finished one.
    announce_stage_start(paths, stage)
    try:
        result = getattr(adapter, method_name)(config, False)
    except Exception as exc:
        result = infrastructure_error_result(stage, exc)
    # The generation records responsible for the iteration this stage judged
    # belong to the attempt itself, so they are recorded with it.
    recorded = record_stage_attempt(
        paths,
        stage,
        result,
        artifacts=_generation_artifact_references(paths, stage, request),
    )
    payload = recorded.payload
    # Where the prepared evidence lives is orchestration, not an observation.
    # Preparation can only run once the attempt has claimed its number, so these
    # references reach the caller through the response while the recorded
    # result.json keeps exactly the contract it was validated against. Nothing
    # is lost: both paths are re-derivable from the run directory.
    references = diagnosis_artifact_references(paths.root, recorded.diagnosis_index)
    if references:
        payload["artifacts"] = {**payload["artifacts"], **references}
    return payload


@app.get(
    "/runs/{run_id}/stages/{stage}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_stage(run_id: str, stage: str) -> dict[str, Any]:
    paths = _open_run(run_id)
    latest = run_store.read_latest(paths, stage)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"no result for stage {stage}")
    if stage == "execution" and isinstance(latest.get("attempt"), int):
        try:
            queue = read_diagnosis_queue(paths.root, latest["attempt"])
        except DiagnosisPreparationError:
            return latest
        latest["artifacts"] = {
            **latest.get("artifacts", {}),
            "failure_report_index": queue["failure_report_index"],
        }
        if queue["eligible_reports"]:
            latest["artifacts"]["failure_report_path"] = queue["eligible_reports"][0][
                "failure_report_path"
            ]
    return latest


@app.get(
    "/runs/{run_id}/diagnosis/execution/{attempt}",
    responses={400: BAD_REQUEST_RESPONSE, 404: NOT_FOUND_RESPONSE, 409: CONFLICT_RESPONSE},
)
def get_diagnosis_queue(run_id: str, attempt: int) -> dict[str, Any]:
    paths, _ = _require_manifest(run_id)
    try:
        return read_diagnosis_queue(paths.root, attempt)
    except DiagnosisPreparationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/runs/{run_id}/refinements",
    responses={400: BAD_REQUEST_RESPONSE, 404: NOT_FOUND_RESPONSE, 409: CONFLICT_RESPONSE, 422: UNPROCESSABLE_RESPONSE},
)
def prepare_run_refinement(
    run_id: str, request: RefinementPrepareRequest
) -> dict[str, Any]:
    paths, manifest = _require_manifest(run_id)
    try:
        return run_store.prepare_refinement(
            paths,
            manifest,
            **request.model_dump(mode="json"),
            diagnoses_root=_diagnoses_root(),
        )
    except run_store.RefinementPreparationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/runs/{run_id}/generations",
    responses={400: BAD_REQUEST_RESPONSE, 404: NOT_FOUND_RESPONSE, 409: CONFLICT_RESPONSE},
)
def record_run_generation(
    run_id: str, request: GenerationRecordRequest
) -> dict[str, Any]:
    paths, manifest = _require_manifest(run_id)
    try:
        generation = run_store.record_generation(
            paths, manifest, **request.model_dump(mode="json")
        )
    except run_store.GenerationRecordError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return generation


@app.get(
    "/runs/{run_id}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_run(run_id: str) -> dict[str, Any]:
    paths, manifest = _require_manifest(run_id)
    return {"run_id": run_id, "manifest": manifest, "stages": run_store.list_stages(paths)}


@app.post(
    "/runs/{run_id}/result",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def record_run_result(run_id: str, request: RunResultRequest) -> dict[str, Any]:
    """Persist where the orchestration ended, with what the run itself recorded."""
    paths, _ = _require_manifest(run_id)
    try:
        result = run_store.record_result(
            paths, request.model_dump(mode="json"), _diagnoses_root()
        )
    except run_store.ResultConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # A run-scoped event: no stage, and the run vocabulary in `run_status`.
    run_store.append_event(
        paths,
        "run_finished",
        run_status=result["status"],
        outcome_code=result["outcome_code"],
    )
    return result


@app.post(
    "/runs/{run_id}/diagnoses",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def record_diagnosis(run_id: str, request: DiagnosisRecordRequest) -> dict[str, Any]:
    """Persist the normalized n8n diagnosis through Python's artifact layer."""
    paths, _ = _require_manifest(run_id)

    diagnosis = request.model_dump(mode="json", exclude_none=True)
    attempt, artifact = run_store.record_diagnosis(paths, diagnosis, _diagnoses_root())
    run_store.append_event(
        paths,
        "diagnosis_recorded",
        stage="diagnosis",
        outcome_code=request.classification,
        attempt=attempt,
    )
    return {**diagnosis, "attempt": attempt, "artifact": artifact}
