"""One launch of the pipeline, and the runs it creates.

A batch is what one press of the master workflow's Start button (or one local
``pipeline run``) produces. It owns nothing a run needs; it exists so that the
runs of one launch are found together and never interleave with another launch:

.. code-block:: text

    <runs-root>/batch_NNN/
    ├── batch.json          immutable: what was launched, and by whom
    ├── batch-result.json   written once when the launch ends
    └── <run-id>/           one run, laid out as ``RunPaths`` describes

The number is claimed the way stage attempts are — by creating the directory —
so two launches started together cannot share one batch. An explicit batch id
is accepted for callers that already have one (a resumed launch, a test) and is
validated like every other identifier that becomes a path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.attempts import claim_attempt, next_free_number
from llm4mtl.run_store.identity import resolve_contained_dir
from llm4mtl.run_store.models import SCHEMA_VERSION
from llm4mtl.serialization.json_io import read_json, write_json_once

BATCH_PREFIX = "batch_"
MANIFEST_FILENAME = "batch.json"
RESULT_FILENAME = "batch-result.json"


class BatchExistsError(RuntimeError):
    """Raised when creating a batch whose manifest already exists."""


class BatchResultConflictError(RuntimeError):
    """Raised when a batch is ended twice with different results."""


@dataclass(frozen=True)
class BatchPaths:
    """Filesystem layout of one batch directory."""

    root: Path

    @property
    def batch_id(self) -> str:
        return self.root.name

    @property
    def manifest(self) -> Path:
        return self.root / MANIFEST_FILENAME

    @property
    def result(self) -> Path:
        return self.root / RESULT_FILENAME


def batch_name(number: int) -> str:
    return f"{BATCH_PREFIX}{number:03d}"


def open_batch(runs_root: Path, batch_id: str) -> BatchPaths:
    """Return the paths of a batch without creating anything.

    Raises :class:`InvalidRunIdError` when ``batch_id`` is malformed or would
    resolve outside ``runs_root``.
    """
    return BatchPaths(resolve_contained_dir(Path(runs_root), batch_id, kind="batch"))


def next_batch_id(runs_root: Path) -> str:
    """The id the next :func:`create_batch` would claim. A preview, not a claim."""
    return batch_name(next_free_number(Path(runs_root), prefix=BATCH_PREFIX))


def create_batch(
    runs_root: Path,
    manifest: dict[str, Any],
    *,
    batch_id: str | None = None,
) -> BatchPaths:
    """Claim a batch directory and write its immutable manifest.

    Without ``batch_id`` the next free ``batch_NNN`` is claimed atomically. With
    one, that exact directory is created, and an existing manifest there is a
    conflict rather than something to replace.
    """
    root = Path(runs_root)
    if batch_id is None:
        number = claim_attempt(
            root, lambda candidate: root / batch_name(candidate), prefix=BATCH_PREFIX
        )
        paths = open_batch(root, batch_name(number))
    else:
        paths = open_batch(root, batch_id)
        paths.root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": paths.batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **manifest,
    }
    validate_artifact("batch-manifest", payload)
    try:
        write_json_once(paths.manifest, payload)
    except FileExistsError as exc:
        raise BatchExistsError(
            f"batch already exists (write-once): {paths.manifest}"
        ) from exc
    return paths


def read_batch_manifest(paths: BatchPaths) -> dict[str, Any] | None:
    if not paths.manifest.is_file():
        return None
    payload = read_json(paths.manifest)
    validate_artifact("batch-manifest", payload)
    return payload


def list_batch_runs(paths: BatchPaths) -> list[str]:
    """The run ids created below this batch, in name order."""
    if not paths.root.is_dir():
        return []
    return sorted(
        child.name
        for child in paths.root.iterdir()
        if child.is_dir() and (child / "manifest.json").is_file()
    )


def record_batch_result(paths: BatchPaths, result: dict[str, Any]) -> dict[str, Any]:
    """Persist how the launch ended, once.

    Re-recording the same ending returns the stored result; a different ending
    is a conflict, because the stored one is what every later reader has seen.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": paths.batch_id,
        **result,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    validate_artifact("batch-result", payload)
    existing = read_batch_result(paths)
    if existing is not None:
        if _without_time(existing) != _without_time(payload):
            raise BatchResultConflictError(
                f"batch already ended as {existing['status']}: {paths.result}"
            )
        return existing
    write_json_once(paths.result, payload)
    return payload


def read_batch_result(paths: BatchPaths) -> dict[str, Any] | None:
    if not paths.result.is_file():
        return None
    payload = read_json(paths.result)
    validate_artifact("batch-result", payload)
    return payload


def _without_time(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "recorded_at"}
