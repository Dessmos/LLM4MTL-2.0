"""FastAPI stage service. Transport only — the pipeline does the work."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from llm4mtl import run_store
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator, generate_run_id
from llm4mtl.languages import language_adapter
from llm4mtl.paths import TARGET, ArtifactRoots, repository_relative
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
    resolve_custom_task_inputs,
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
    BatchCreateRequest,
    BatchCreateResponse,
    BatchResultRequest,
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


def _artifact_roots() -> ArtifactRoots:
    """The artifact tree this service writes. One function, so a test redirects it."""
    return TARGET.artifact_roots


def _open_batch(batch_id: str) -> run_store.BatchPaths:
    """Open a batch, translating a malformed or escaping id into a 400."""
    try:
        return run_store.open_batch(_artifact_roots().runs, batch_id)
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_batch(batch_id: str) -> tuple[run_store.BatchPaths, dict[str, Any]]:
    batch = _open_batch(batch_id)
    manifest = run_store.read_batch_manifest(batch)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"unknown batch: {batch_id}")
    return batch, manifest


def _open_run(batch_id: str, run_id: str) -> run_store.RunPaths:
    """Open a run of a known batch, translating a malformed id into a 400."""
    batch, _ = _require_batch(batch_id)
    try:
        return run_store.open_run(batch.root, run_id)
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_manifest(
    batch_id: str, run_id: str
) -> tuple[run_store.RunPaths, dict[str, Any]]:
    paths = _open_run(batch_id, run_id)
    manifest = run_store.read_manifest(paths)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"unknown run: {run_id}")
    return paths, manifest


def _run_diagnoses(batch_id: str, run_id: str):
    """Where this run's verdicts live: asked of the layout, never derived."""
    return _artifact_roots().run_diagnoses_dir(batch_id, run_id)


def _locations(directory) -> dict[str, str]:
    """A directory as the repository names it and as n8n reaches it.

    n8n receives both spellings from here and builds no artifact path of its
    own: the repository-relative one is what Python cites in every artifact, the
    mounted one is what the workflow's file nodes can open.
    """
    return {
        "dir": repository_relative(directory),
        "n8n_dir": _artifact_roots().n8n_path(directory),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/prompt-inputs/resolve",
    responses={422: UNPROCESSABLE_RESPONSE},
)
def resolve_prompt_inputs(request: PromptInputsRequest) -> dict[str, Any]:
    """Return only the exact LLM inputs of this task: a custom task's own
    metamodel when the request carries one, its task contract's otherwise."""
    try:
        if request.metamodel is not None:
            return resolve_custom_task_inputs(
                request.language, request.task, request.metamodel
            ).to_dict()
        return resolve_task_inputs(request.language, request.task).to_dict()
    except TaskInputResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/batches",
    response_model=BatchCreateResponse,
    responses={
        400: BAD_REQUEST_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: UNPROCESSABLE_RESPONSE,
    },
)
def create_batch(request: BatchCreateRequest) -> BatchCreateResponse:
    """Claim the directory one launch's runs are created in.

    Without ``batch_id`` the next free ``batch_NNN`` is claimed atomically, so
    two launches started together cannot share one.
    """
    manifest: dict[str, Any] = {
        "run_mode": request.run_mode,
        "pipeline_variant": request.pipeline_variant,
        "command": None,
    }
    if request.config is not None:
        manifest["config"] = request.config
    if request.n8n is not None:
        manifest["n8n"] = request.n8n.model_dump()
    try:
        batch = run_store.create_batch(
            _artifact_roots().runs, manifest, batch_id=request.batch_id
        )
    except run_store.BatchExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"batch already exists: {request.batch_id}"
        ) from exc
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    locations = _locations(batch.root)
    return BatchCreateResponse(
        batch_id=batch.batch_id,
        batch_dir=locations["dir"],
        n8n_batch_dir=locations["n8n_dir"],
    )


@app.get(
    "/batches/{batch_id}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_batch(batch_id: str) -> dict[str, Any]:
    batch, manifest = _require_batch(batch_id)
    return {
        "batch_id": batch.batch_id,
        "manifest": manifest,
        "runs": run_store.list_batch_runs(batch),
        "result": run_store.read_batch_result(batch),
    }


@app.post(
    "/batches/{batch_id}/result",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def record_batch_result(batch_id: str, request: BatchResultRequest) -> dict[str, Any]:
    """Persist how the launch ended, once, next to the runs it created."""
    batch, _ = _require_batch(batch_id)
    try:
        return run_store.record_batch_result(batch, request.model_dump(mode="json"))
    except run_store.BatchResultConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post(
    "/batches/{batch_id}/runs",
    response_model=RunCreateResponse,
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: UNPROCESSABLE_RESPONSE,
    },
)
def create_run(batch_id: str, request: RunCreateRequest) -> RunCreateResponse:
    if request.task == "all":
        raise HTTPException(
            status_code=422,
            detail="a run must fix one concrete task; expand all tasks through a matrix",
        )
    batch, _ = _require_batch(batch_id)
    custom = request.custom_task
    # A custom task is its own identity axis: nothing about it is resolved
    # through another task, so its name is the task the manifest records.
    run_id = request.run_id or generate_run_id(
        PipelineConfig(
            language=request.language,
            tasks=[custom.name if custom is not None else request.task],
        )
    )
    try:
        provenance = build_provenance(
            request.language,
            request.task,
            custom_task_prompt=custom.prompt if custom is not None else None,
            custom_task_metamodel=custom.metamodel if custom is not None else None,
        )
        if custom is not None:
            provenance["custom_task"] = {"name": custom.name}
        manifest = {
            "batch_id": batch.batch_id,
            "language": request.language,
            "task": request.task,
            "transformation_model": request.transformation_model,
            "test_generation_model": request.test_generation_model,
            "transformation_strategy": request.transformation_strategy,
            "test_generation_strategy": request.test_generation_strategy,
            "seed": request.seed,
            "pipeline_variant": request.pipeline_variant,
            "preset": request.preset,
            "provenance": provenance,
        }
        if request.experiment_config is not None:
            manifest["experiment_config"] = request.experiment_config.model_dump()
        paths = run_store.create_run(
            batch.root,
            run_id,
            manifest,
            task_prompt=custom.prompt if custom is not None else None,
            metamodel=custom.metamodel if custom is not None else None,
        )
    except run_store.ManifestExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"run already exists: {run_id}"
        ) from exc
    except InvalidRunIdError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProvenanceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    locations = _locations(paths.root)
    return RunCreateResponse(
        run_id=run_id,
        batch_id=batch.batch_id,
        run_dir=locations["dir"],
        n8n_run_dir=locations["n8n_dir"],
    )


def _stage_config(
    run_id: str, manifest: dict[str, Any], request: StageRunRequest
) -> PipelineConfig:
    """Build stage selection exclusively from the immutable manifest."""
    language = manifest.get("language")
    if not isinstance(language, str) or not language:
        raise HTTPException(
            status_code=409, detail="run manifest has no language identity"
        )
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
    extension = (
        language_adapter(config.language)
        .reference_transformation(config.tasks[0])
        .suffix
    )
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
    "/batches/{batch_id}/runs/{run_id}/stages/{stage}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def run_stage(
    batch_id: str, run_id: str, stage: str, request: StageRunRequest
) -> dict[str, Any]:
    if stage not in STAGE_DISPATCH:
        raise HTTPException(status_code=404, detail=f"unknown stage: {stage}")
    paths, manifest = _require_manifest(batch_id, run_id)
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
    "/batches/{batch_id}/runs/{run_id}/stages/{stage}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_stage(batch_id: str, run_id: str, stage: str) -> dict[str, Any]:
    paths = _open_run(batch_id, run_id)
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
    "/batches/{batch_id}/runs/{run_id}/diagnosis/execution/{attempt}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def get_diagnosis_queue(batch_id: str, run_id: str, attempt: int) -> dict[str, Any]:
    paths, _ = _require_manifest(batch_id, run_id)
    try:
        return read_diagnosis_queue(paths.root, attempt)
    except DiagnosisPreparationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post(
    "/batches/{batch_id}/runs/{run_id}/refinements",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: UNPROCESSABLE_RESPONSE,
    },
)
def prepare_run_refinement(
    batch_id: str, run_id: str, request: RefinementPrepareRequest
) -> dict[str, Any]:
    paths, manifest = _require_manifest(batch_id, run_id)
    try:
        prepared = run_store.prepare_refinement(
            paths,
            manifest,
            **request.model_dump(mode="json"),
            run_diagnoses=_run_diagnoses(batch_id, run_id),
        )
    except run_store.RefinementPreparationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # The store names the prompt within the run; where n8n reads it from is
    # this transport's knowledge.
    prompt_path = _artifact_roots().n8n_path(paths.root / prepared["prompt_file"])
    return {**prepared, "prompt_path": prompt_path}


@app.post(
    "/batches/{batch_id}/runs/{run_id}/generations",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def record_run_generation(
    batch_id: str, run_id: str, request: GenerationRecordRequest
) -> dict[str, Any]:
    paths, manifest = _require_manifest(batch_id, run_id)
    try:
        generation = run_store.record_generation(
            paths, manifest, **request.model_dump(mode="json")
        )
    except run_store.GenerationRecordError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return generation


@app.get(
    "/batches/{batch_id}/runs/{run_id}",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def get_run(batch_id: str, run_id: str) -> dict[str, Any]:
    paths, manifest = _require_manifest(batch_id, run_id)
    locations = _locations(paths.root)
    return {
        "run_id": run_id,
        "batch_id": batch_id,
        "run_dir": locations["dir"],
        "n8n_run_dir": locations["n8n_dir"],
        "manifest": manifest,
        "stages": run_store.list_stages(paths),
    }


@app.post(
    "/batches/{batch_id}/runs/{run_id}/result",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
    },
)
def record_run_result(
    batch_id: str, run_id: str, request: RunResultRequest
) -> dict[str, Any]:
    """Persist where the orchestration ended, with what the run itself recorded."""
    paths, _ = _require_manifest(batch_id, run_id)
    try:
        result = run_store.record_result(
            paths, request.model_dump(mode="json"), _run_diagnoses(batch_id, run_id)
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
    "/batches/{batch_id}/runs/{run_id}/diagnoses",
    responses={
        400: BAD_REQUEST_RESPONSE,
        404: NOT_FOUND_RESPONSE,
    },
)
def record_diagnosis(
    batch_id: str, run_id: str, request: DiagnosisRecordRequest
) -> dict[str, Any]:
    """Persist the normalized n8n diagnosis through Python's artifact layer."""
    paths, _ = _require_manifest(batch_id, run_id)

    diagnosis = request.model_dump(mode="json", exclude_none=True)
    attempt, written = run_store.record_diagnosis(
        paths, diagnosis, _run_diagnoses(batch_id, run_id)
    )
    # Reported relative to the diagnoses area, so the caller sees the batch and
    # run it was filed under without knowing how that area is laid out.
    artifact = (
        written.resolve()
        .relative_to(_artifact_roots().diagnoses.resolve())
        .as_posix()
    )
    run_store.append_event(
        paths,
        "diagnosis_recorded",
        stage="diagnosis",
        outcome_code=request.classification,
        attempt=attempt,
    )
    return {**diagnosis, "attempt": attempt, "artifact": artifact}
