"""Experiment store (public facade): immutable experiment manifest + a mutable
run-index that links the runs of a matrix/ablation together.
"""

from __future__ import annotations

import fcntl
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.experiment_store.models import SCHEMA_VERSION, ExperimentPaths
from llm4mtl.run_store.identity import resolve_contained_dir
from llm4mtl.run_store.manifest import ManifestExistsError
from llm4mtl.serialization.json_io import read_json, write_json, write_json_once


def open_experiment(experiments_root: Path, experiment_id: str) -> ExperimentPaths:
    """Return the paths of an experiment, rejecting ids that escape the root."""
    return ExperimentPaths(
        resolve_contained_dir(Path(experiments_root), experiment_id, kind="experiment")
    )


def create_experiment(
    experiments_root: Path,
    experiment_id: str,
    manifest: dict[str, Any],
) -> ExperimentPaths:
    """Create the experiment directory with an immutable manifest and empty index."""
    paths = open_experiment(experiments_root, experiment_id)
    paths.root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **manifest,
    }
    validate_artifact("experiment-manifest", payload)
    try:
        write_json_once(paths.manifest, payload)
    except FileExistsError as exc:
        raise ManifestExistsError(
            f"experiment manifest already exists: {paths.manifest}"
        ) from exc
    index = {"schema_version": SCHEMA_VERSION, "runs": []}
    validate_artifact("run-index", index)
    try:
        write_json_once(paths.run_index, index)
    except FileExistsError:
        # The manifest create above is the ownership claim. A pre-existing index
        # without that manifest is corruption, not something to overwrite.
        paths.manifest.unlink(missing_ok=True)
        raise
    return paths


def add_run(paths: ExperimentPaths, run_id: str) -> None:
    """Append a run id to the experiment's run-index (idempotent)."""
    resolve_contained_dir(paths.root / "_run-id-validation", run_id, kind="run")
    lock_path = paths.root / ".run-index.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        index = _read_index(paths)
        runs: list[str] = list(index["runs"])
        if run_id not in runs:
            runs.append(run_id)
        index["runs"] = runs
        validate_artifact("run-index", index)
        write_json(paths.run_index, index)


def list_runs(paths: ExperimentPaths) -> list[str]:
    if not paths.run_index.exists():
        return []
    return list(_read_index(paths)["runs"])


def read_manifest(paths: ExperimentPaths) -> dict[str, Any] | None:
    if not paths.manifest.exists():
        return None
    payload = read_json(paths.manifest)
    validate_artifact("experiment-manifest", payload)
    return payload


def _read_index(paths: ExperimentPaths) -> dict[str, Any]:
    payload = read_json(paths.run_index)
    validate_artifact("run-index", payload)
    return payload


__all__ = [
    "SCHEMA_VERSION",
    "ExperimentPaths",
    "open_experiment",
    "create_experiment",
    "add_run",
    "list_runs",
    "read_manifest",
]
