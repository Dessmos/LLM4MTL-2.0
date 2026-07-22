"""Run-centric artifact store (public facade).

A run directory (``artifacts/work/runs/<run-id>/``) has three owners with distinct
write invariants: an immutable ``manifest.json`` (write-once), an append-only
``events.jsonl`` timeline, and per-stage results stored as immutable
``attempts/attempt-NNN/`` with a mutable ``latest.json`` projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.run_store.events import append_event, read_events
from llm4mtl.run_store.manifest import ManifestExistsError, read_manifest, write_manifest
from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths
from llm4mtl.run_store.stages import list_stages, next_attempt, read_latest, record_attempt


def open_run(runs_root: Path, run_id: str) -> RunPaths:
    """Return the :class:`RunPaths` for a run without creating anything."""
    return RunPaths((Path(runs_root) / run_id).resolve())


def create_run(
    runs_root: Path,
    run_id: str,
    manifest: dict[str, Any],
    *,
    force: bool = False,
) -> RunPaths:
    """Create the run directory, write the immutable manifest, and open the event log."""
    paths = open_run(runs_root, run_id)
    paths.root.mkdir(parents=True, exist_ok=True)
    write_manifest(paths, {"run_id": run_id, **manifest}, force=force)
    append_event(paths, "run_created")
    return paths


__all__ = [
    "SCHEMA_VERSION",
    "RunPaths",
    "ManifestExistsError",
    "open_run",
    "create_run",
    "write_manifest",
    "read_manifest",
    "append_event",
    "read_events",
    "next_attempt",
    "record_attempt",
    "read_latest",
    "list_stages",
]
