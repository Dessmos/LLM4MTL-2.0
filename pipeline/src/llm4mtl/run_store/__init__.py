"""Run-centric artifact store (public facade).

A run directory (``artifacts/work/runs/<run-id>/``) has three owners with distinct
write invariants: an immutable ``manifest.json`` (write-once), an append-only
``events.jsonl`` timeline, and per-stage results stored as immutable
``attempts/attempt-NNN/``, with the latest result derived from them on read.

Run ids are untrusted input and are validated for containment before they become
a path; attempt directories are claimed atomically so concurrent stage calls
cannot overwrite one another's evidence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.run_store.attempts import AttemptAllocationError
from llm4mtl.run_store.events import append_event, read_events
from llm4mtl.run_store.identity import InvalidRunIdError, resolve_contained_dir
from llm4mtl.run_store.manifest import ManifestExistsError, read_manifest, write_manifest
from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths
from llm4mtl.run_store.responses import record_diagnosis
from llm4mtl.run_store.stages import list_stages, read_latest, record_attempt


def open_run(runs_root: Path, run_id: str) -> RunPaths:
    """Return the :class:`RunPaths` for a run without creating anything.

    Raises :class:`InvalidRunIdError` when ``run_id`` is malformed or would
    resolve outside ``runs_root``.
    """
    return RunPaths(resolve_contained_dir(Path(runs_root), run_id, kind="run"))


def create_run(runs_root: Path, run_id: str, manifest: dict[str, Any]) -> RunPaths:
    """Create the run directory, write the immutable manifest, and open the event log."""
    paths = open_run(runs_root, run_id)
    paths.root.mkdir(parents=True, exist_ok=True)
    write_manifest(paths, {"run_id": run_id, **manifest})
    append_event(paths, "run_created")
    return paths


__all__ = [
    "SCHEMA_VERSION",
    "RunPaths",
    "AttemptAllocationError",
    "InvalidRunIdError",
    "ManifestExistsError",
    "open_run",
    "create_run",
    "write_manifest",
    "read_manifest",
    "append_event",
    "read_events",
    "record_attempt",
    "read_latest",
    "list_stages",
    "record_diagnosis",
]
