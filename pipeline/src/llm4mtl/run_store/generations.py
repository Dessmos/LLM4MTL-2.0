"""Write-once provenance for every generation and refinement LLM call."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.conventions import frozen_task_prompt, language_config
from llm4mtl.run_store.models import RECORDED_AT, RunPaths, without_recorded_at
from llm4mtl.serialization.json_io import (
    JsonDocumentConflictError,
    write_json_once_or_match,
)

SCHEMA_VERSION = "1.0"
# The artifact types a generation or refinement call produces.
SEMANTIC_TEST_ARTIFACT = "semantic-test"
TRANSFORMATION_ARTIFACT = "transformation"
# The response directory, below a run, of each artifact type's generations.
SEMANTIC_TEST_GENERATION = "semantic-test-generation"
TRANSFORMATION_GENERATION = "transformation-generation"


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


def write_metamodel(paths: RunPaths, metamodel: str) -> Path:
    """Keep the custom task metamodel a run was created with, exactly once."""
    if paths.metamodel.exists():
        raise GenerationRecordError(f"metamodel already recorded: {paths.metamodel}")
    paths.metamodel.write_text(metamodel, encoding="utf-8")
    return paths.metamodel


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
    """Record, once, which files one generation call read and wrote.

    A retry that records the same facts reads the first record back; different
    facts for the same iteration raise :class:`GenerationRecordError`.
    """
    files = _generation_files(paths, manifest, artifact_type, iteration)
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
        **_file_links(paths, files, iteration),
        RECORDED_AT: datetime.now(timezone.utc).isoformat(),
    }
    validate_artifact("generation-result", payload)
    return _write_record_once(paths.generation_record(artifact_type, iteration), payload)


@dataclass(frozen=True)
class _GenerationFiles:
    """The files one generation call read and wrote.

    ``input_artifact`` and ``refinement_request`` exist only for a refinement,
    that is for an iteration above 0.
    """

    prompt: Path
    output_artifact: Path
    input_artifact: Path | None
    refinement_request: Path | None


def _generation_files(
    paths: RunPaths, manifest: dict[str, Any], artifact_type: str, iteration: int
) -> _GenerationFiles:
    """Find the files of one generation call; raise when one is missing."""
    operation, suffix = _operation_and_suffix(manifest, artifact_type)
    response_name = f"{manifest['task']}.{suffix}"
    output = paths.generation_response(operation, iteration, response_name)
    _require_file(output, "raw generation output is missing")
    if iteration == 0:
        return _GenerationFiles(
            prompt=_prompt_file(paths, manifest, artifact_type, iteration),
            output_artifact=output,
            input_artifact=None,
            refinement_request=None,
        )
    request = paths.refinement_request(artifact_type, iteration)
    _require_file(request, "refinement request is missing")
    prompt = _prompt_file(paths, manifest, artifact_type, iteration)
    previous = paths.generation_response(operation, iteration - 1, response_name)
    _require_file(previous, "input generation artifact is missing")
    return _GenerationFiles(
        prompt=prompt,
        output_artifact=output,
        input_artifact=previous,
        refinement_request=request,
    )


def _prompt_file(
    paths: RunPaths, manifest: dict[str, Any], artifact_type: str, iteration: int
) -> Path:
    """The prompt a generation call was sent.

    Semantic-test workflows archive the full prompt beside their response.
    Transformation workflows do not. Then a refinement falls back to the prompt
    Python prepared, and an initial generation to the run's task prompt.
    """
    operation = _operation_for_artifact_type(artifact_type)
    archived = paths.generation_prompt(operation, iteration)
    if archived.is_file():
        return archived
    if iteration > 0:
        prepared = paths.refinement_prompt(artifact_type, iteration)
        if prepared.is_file():
            return prepared
    return task_prompt_source(paths, manifest)


def _file_links(
    paths: RunPaths, files: _GenerationFiles, iteration: int
) -> dict[str, Any]:
    """Which iteration the call read and wrote, and the files it used."""
    return {
        "input_artifact_iteration": iteration - 1 if iteration > 0 else None,
        "created_artifact_iteration": iteration,
        "prompt": _file_fact(paths, files.prompt),
        "input_artifact": _optional_file_fact(paths, files.input_artifact),
        "output_artifact": _file_fact(paths, files.output_artifact),
        "refinement_request": _optional_file_fact(paths, files.refinement_request),
    }


def _write_record_once(destination: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Write the record once; a retry must record the same facts."""
    try:
        return write_json_once_or_match(
            destination,
            payload,
            comparable=without_recorded_at,
            check_stored=_validate_generation_record,
        )
    except JsonDocumentConflictError as exc:
        raise GenerationRecordError(
            f"generation attempt already has different provenance: {destination}"
        ) from exc


def _require_file(path: Path, problem: str) -> None:
    if not path.is_file():
        raise GenerationRecordError(f"{problem}: {path}")


def _validate_generation_record(record: dict[str, Any]) -> None:
    validate_artifact("generation-result", record)


def _operation_and_suffix(
    manifest: dict[str, Any], artifact_type: str
) -> tuple[str, str]:
    operation = _operation_for_artifact_type(artifact_type)
    if artifact_type == SEMANTIC_TEST_ARTIFACT:
        return operation, "md"
    return operation, language_config(str(manifest["language"])).language_key


def _operation_for_artifact_type(artifact_type: str) -> str:
    if artifact_type == SEMANTIC_TEST_ARTIFACT:
        return SEMANTIC_TEST_GENERATION
    if artifact_type == TRANSFORMATION_ARTIFACT:
        return TRANSFORMATION_GENERATION
    raise GenerationRecordError(f"unsupported artifact type: {artifact_type}")


def _optional_file_fact(paths: RunPaths, path: Path | None) -> dict[str, Any] | None:
    return None if path is None else _file_fact(paths, path)


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
