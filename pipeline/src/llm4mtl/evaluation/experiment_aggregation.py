"""Aggregate stage outcomes across the runs of an experiment.

Reads each run from the run store (manifest + a stage's ``latest.json``) and groups
outcome codes by ``pipeline_variant`` / transformation model / strategy. This is the
experiment layer: run-level results stay per run; aggregation happens over many runs.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from llm4mtl import run_store


def _group_key(manifest: dict[str, Any]) -> str:
    return "/".join(
        [
            str(manifest.get("pipeline_variant", "full")),
            str(manifest.get("transformation_model", "")),
            str(manifest.get("strategy", "")),
        ]
    )


def aggregate_stage(runs_root: Path, run_ids: list[str], stage: str) -> dict[str, Any]:
    """Count outcome codes for ``stage`` across the given runs, grouped and total."""
    by_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    totals: dict[str, int] = defaultdict(int)
    counted = 0
    for run_id in run_ids:
        paths = run_store.open_run(runs_root, run_id)
        manifest = run_store.read_manifest(paths)
        latest = run_store.read_latest(paths, stage)
        if manifest is None or latest is None:
            continue
        counted += 1
        code = str(latest.get("outcome_code", "UNKNOWN"))
        by_group[_group_key(manifest)][code] += 1
        totals[code] += 1
    return {
        "schema_version": "1.0",
        "stage": stage,
        "runs": counted,
        "totals": dict(totals),
        "by_group": {group: dict(counts) for group, counts in by_group.items()},
    }
