"""Experiment store (public facade): immutable experiment manifest + a mutable
run-index that links the runs of a matrix/ablation together.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.experiment_store.models import SCHEMA_VERSION, ExperimentPaths
from llm4mtl.run_store.manifest import ManifestExistsError
from llm4mtl.serialization.json_io import read_json, write_json


def open_experiment(experiments_root: Path, experiment_id: str) -> ExperimentPaths:
    return ExperimentPaths((Path(experiments_root) / experiment_id).resolve())


def create_experiment(
    experiments_root: Path,
    experiment_id: str,
    manifest: dict[str, Any],
    *,
    force: bool = False,
) -> ExperimentPaths:
    """Create the experiment directory with an immutable manifest and empty index."""
    paths = open_experiment(experiments_root, experiment_id)
    if paths.manifest.exists() and not force:
        raise ManifestExistsError(f"experiment manifest already exists: {paths.manifest}")
    paths.root.mkdir(parents=True, exist_ok=True)
    write_json(
        paths.manifest,
        {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": experiment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            **manifest,
        },
    )
    if not paths.run_index.exists():
        write_json(paths.run_index, {"schema_version": SCHEMA_VERSION, "runs": []})
    return paths


def add_run(paths: ExperimentPaths, run_id: str) -> None:
    """Append a run id to the experiment's run-index (idempotent)."""
    index = read_json(paths.run_index) if paths.run_index.exists() else {"schema_version": SCHEMA_VERSION, "runs": []}
    runs: list[str] = list(index.get("runs", []))
    if run_id not in runs:
        runs.append(run_id)
    index["runs"] = runs
    write_json(paths.run_index, index)


def list_runs(paths: ExperimentPaths) -> list[str]:
    if not paths.run_index.exists():
        return []
    return list(read_json(paths.run_index).get("runs", []))


def read_manifest(paths: ExperimentPaths) -> dict[str, Any] | None:
    return read_json(paths.manifest) if paths.manifest.exists() else None


__all__ = [
    "SCHEMA_VERSION",
    "ExperimentPaths",
    "open_experiment",
    "create_experiment",
    "add_run",
    "list_runs",
    "read_manifest",
]
