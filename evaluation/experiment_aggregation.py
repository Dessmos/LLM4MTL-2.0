"""Aggregate stage outcomes across the runs of an experiment.

Reads each run from the run store (manifest + a stage's latest attempt) and groups
outcome codes by every model/strategy identity axis. This is the experiment
layer: run-level results stay per run; aggregation happens over many runs.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl import run_store
from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.serialization.json_io import read_json


GENERATION_REFERENCE_ROLES = {
    "transformation_generation_record": "transformation",
    "semantic_test_generation_record": "semantic-test",
}
EXPECTED_GENERATION_ROLES = {
    "extract": {"semantic-test"},
    "technical-validation": {"semantic-test"},
    "reference-validation": {"semantic-test"},
    "syntax-validation": {"transformation"},
    "execution": {"transformation", "semantic-test"},
}


@dataclass(frozen=True)
class GenerationAttribution:
    artifact_type: str
    artifact_iteration: int
    provider: str
    model: str


def _group_key(manifest: dict[str, Any]) -> str:
    return "/".join(
        [
            str(manifest.get("pipeline_variant", "full")),
            str(manifest.get("transformation_model", "")),
            str(manifest.get("transformation_strategy", "")),
            str(manifest.get("test_generation_model", "")),
            str(manifest.get("test_generation_strategy", "")),
        ]
    )


def aggregate_stage(runs_root: Path, run_ids: list[str], stage: str) -> dict[str, Any]:
    """Count outcomes by configured axes and their responsible generations."""
    by_group: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    generation_groups: dict[str, dict[str, Any]] = {}
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
        attributions = _generation_attributions(paths, latest)
        generation_key = _generation_group_key(manifest, attributions)
        if generation_key not in generation_groups:
            responsible = {
                attribution.artifact_type: {
                    "artifact_iteration": attribution.artifact_iteration,
                    "provider": attribution.provider,
                    "model": attribution.model,
                }
                for attribution in attributions
            }
            generation_groups[generation_key] = {
                "configured": {
                    "pipeline_variant": str(manifest.get("pipeline_variant", "full")),
                    "transformation_model_family": manifest.get("transformation_model"),
                    "transformation_strategy": manifest.get("transformation_strategy"),
                    "test_generation_model_family": manifest.get(
                        "test_generation_model"
                    ),
                    "test_generation_strategy": manifest.get(
                        "test_generation_strategy"
                    ),
                },
                "responsible_generations": responsible,
                "generation_provenance_complete": (
                    set(responsible) == EXPECTED_GENERATION_ROLES.get(stage, set())
                ),
                "outcomes": defaultdict(int),
            }
        generation_groups[generation_key]["outcomes"][code] += 1
        totals[code] += 1
    return {
        "schema_version": "1.0",
        "stage": stage,
        "runs": counted,
        "totals": dict(totals),
        "by_group": {group: dict(counts) for group, counts in by_group.items()},
        "by_configured_group": {
            group: dict(counts) for group, counts in by_group.items()
        },
        "by_generation": [
            {
                **group,
                "outcomes": dict(group["outcomes"]),
            }
            for _, group in sorted(generation_groups.items())
        ],
    }


def _generation_attributions(
    paths: run_store.RunPaths, latest: dict[str, Any]
) -> tuple[GenerationAttribution, ...]:
    artifacts = latest.get("artifacts")
    if not isinstance(artifacts, dict):
        return ()
    attributions: list[GenerationAttribution] = []
    for reference_key, artifact_type in GENERATION_REFERENCE_ROLES.items():
        reference = artifacts.get(reference_key)
        if not isinstance(reference, str):
            continue
        generation = _read_generation_reference(paths, reference, artifact_type)
        attributions.append(
            GenerationAttribution(
                artifact_type=artifact_type,
                artifact_iteration=int(generation["created_artifact_iteration"]),
                provider=str(generation["provider"]),
                model=str(generation["model"]),
            )
        )
    return tuple(sorted(attributions, key=lambda item: item.artifact_type))


def _read_generation_reference(
    paths: run_store.RunPaths, reference: str, artifact_type: str
) -> dict[str, Any]:
    candidate = (paths.root / reference).resolve()
    try:
        candidate.relative_to(paths.root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"generation reference escapes run {paths.root.name}: {reference}"
        ) from exc
    if not candidate.is_file():
        raise ValueError(f"generation reference is missing: {reference}")
    generation = read_json(candidate)
    validate_artifact("generation-result", generation)
    iteration = generation.get("created_artifact_iteration")
    if (
        generation.get("run_id") != paths.root.name
        or generation.get("artifact_type") != artifact_type
        or not isinstance(iteration, int)
        or candidate != paths.generation_record(artifact_type, iteration).resolve()
    ):
        raise ValueError(
            f"generation reference identity does not match stage: {reference}"
        )
    return generation


def _generation_group_key(
    manifest: dict[str, Any], attributions: tuple[GenerationAttribution, ...]
) -> str:
    return json.dumps(
        {
            "configured": _group_key(manifest),
            "responsible": [
                {
                    "artifact_type": item.artifact_type,
                    "artifact_iteration": item.artifact_iteration,
                    "provider": item.provider,
                    "model": item.model,
                }
                for item in attributions
            ],
        },
        sort_keys=True,
    )
