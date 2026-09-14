"""Write-once provenance for every generation and refinement LLM call."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.conventions import frozen_task_prompt, language_config
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import read_json, write_json_once

SCHEMA_VERSION = "1.0"


class GenerationRecordError(ValueError):
    """Raised when generation evidence is missing or would be overwritten."""


def prepare_generation_response_directory(
    paths: RunPaths, *, artifact_type: str, iteration: int
) -> Path:
    """Create the directory an n8n generation workflow writes into.

    n8n's file-write node resolves the parent directory before writing and does
    not create a missing run-scoped path. Python owns filesystem preparation,
    so every generation entry point calls this before control reaches an LLM.
    """
    if iteration < 0:
        raise GenerationRecordError("generation iteration must be non-negative")
    operation = _operation_for_artifact_type(artifact_type)
    directory = paths.generation_iteration_dir(operation, iteration)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def task_prompt_source(paths: RunPaths, manifest: dict[str, Any]) -> Path:
    """The task specification this run's generators were given.

    A run created with a custom task prompt keeps it as ``task-prompt.md`` and
    every generator reads that copy; every other run reads the frozen benchmark
    prompt. Stated once, so generation provenance and refinement cannot cite
    different specifications for the same run.
    """
    if paths.task_prompt.is_file():
        return paths.task_prompt
    return frozen_task_prompt(
        language_config(str(manifest["language"])), str(manifest["task"])
    )


def write_task_prompt(paths: RunPaths, prompt: str) -> Path:
    """Keep the custom task prompt a run was created with, exactly once."""
    if paths.task_prompt.exists():
        raise GenerationRecordError(f"task prompt already recorded: {paths.task_prompt}")
    paths.task_prompt.write_text(prompt, encoding="utf-8")
    return paths.task_prompt


def record_generation(
    paths: RunPaths,
    manifest: dict[str, Any],
    *,
    artifact_type: str,
    iteration: int,
    purpose: str,
    provider: str,
    model: str,
    strategy: str | None,
) -> dict[str, Any]:
    operation, suffix = _operation_and_suffix(manifest, artifact_type)
    output = paths.generation_response(
        operation, iteration, f"{manifest['task']}.{suffix}"
    )
    if not output.is_file():
        raise GenerationRecordError(f"raw generation output is missing: {output}")

    request_path = paths.refinement_dir(artifact_type, iteration) / "request.json"
    if iteration > 0 and not request_path.is_file():
        raise GenerationRecordError(f"refinement request is missing: {request_path}")
    # Semantic-test workflows archive the fully assembled prompt beside their
    # response. Transformation exports currently do not, so refinement falls
    # back to Python's exact prepared prompt and initial generation to the
    # task prompt the run was created with.
    prompt = paths.generation_iteration_dir(operation, iteration) / "prompt.md"
    if not prompt.is_file() and iteration > 0:
        prompt = paths.refinement_dir(artifact_type, iteration) / "prompt.md"
    if not prompt.is_file():
        prompt = task_prompt_source(paths, manifest)
    previous = None
    if iteration > 0:
        previous = paths.generation_response(
            operation, iteration - 1, f"{manifest['task']}.{suffix}"
        )
        if not previous.is_file():
            raise GenerationRecordError(
                f"input generation artifact is missing: {previous}"
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": paths.root.name,
        "language": manifest["language"],
        "task": manifest["task"],
        "artifact_type": artifact_type,
        "iteration": iteration,
        "purpose": purpose,
        "provider": provider,
        "model": model,
        "strategy": strategy,
        "input_artifact_iteration": iteration - 1 if iteration > 0 else None,
        "created_artifact_iteration": iteration,
        "prompt": _file_fact(paths, prompt),
        "input_artifact": _file_fact(paths, previous) if previous is not None else None,
        "output_artifact": _file_fact(paths, output),
        "refinement_request": _file_fact(paths, request_path)
        if iteration > 0
        else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    validate_artifact("generation-result", payload)
    destination = paths.generation_record(artifact_type, iteration)
    try:
        write_json_once(destination, payload)
    except FileExistsError:
        existing = read_json(destination)
        validate_artifact("generation-result", existing)
        if _without_time(existing) != _without_time(payload):
            raise GenerationRecordError(
                f"generation attempt already has different provenance: {destination}"
            )
        return existing
    return payload


def _operation_and_suffix(
    manifest: dict[str, Any], artifact_type: str
) -> tuple[str, str]:
    operation = _operation_for_artifact_type(artifact_type)
    if artifact_type == "semantic-test":
        return operation, "md"
    return operation, language_config(str(manifest["language"])).language_key


def _operation_for_artifact_type(artifact_type: str) -> str:
    if artifact_type == "semantic-test":
        return "semantic-test-generation"
    if artifact_type == "transformation":
        return "transformation-generation"
    raise GenerationRecordError(f"unsupported artifact type: {artifact_type}")


def _file_fact(paths: RunPaths, path: Path) -> dict[str, Any]:
    content = Path(path).read_bytes()
    try:
        cited = Path(path).resolve().relative_to(paths.root.resolve()).as_posix()
    except ValueError:
        cited = Path(path).resolve().as_posix()
    return {
        "path": cited,
        "sha256": hashlib.sha256(content).hexdigest(),
        "bytes": len(content),
    }


def _without_time(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "recorded_at"}
