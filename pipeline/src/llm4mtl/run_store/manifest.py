"""Immutable run manifest (write-once).

The manifest is the run's identity: language, task, models, generation
strategies, variant, seed, and the provenance needed to reproduce the run. Everything downstream is
attributed through it, so it is written once, validated against
``schemas/manifest.schema.json``, and never edited afterwards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths
from llm4mtl.serialization.json_io import read_json, write_json_once


class ManifestExistsError(RuntimeError):
    """Raised when writing a manifest that already exists; manifests are write-once."""


def write_manifest(paths: RunPaths, manifest: dict[str, Any]) -> dict[str, Any]:
    """Write the run manifest exactly once.

    There is no override. A manifest that could be replaced is not an identity:
    every stage result, event, and metric in the run directory is attributed
    through it, so rewriting it silently re-labels evidence that was produced
    under the old identity. Re-running with different identity means a new run.
    """
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, **manifest}
    payload.setdefault("started_at", datetime.now(timezone.utc).isoformat())
    validate_artifact("manifest", payload)
    try:
        write_json_once(paths.manifest, payload)
    except FileExistsError as exc:
        raise ManifestExistsError(
            f"manifest already exists (write-once): {paths.manifest}"
        ) from exc
    return payload


def read_manifest(paths: RunPaths) -> dict[str, Any] | None:
    if not paths.manifest.exists():
        return None
    payload = read_json(paths.manifest)
    validate_artifact("manifest", payload)
    return payload
