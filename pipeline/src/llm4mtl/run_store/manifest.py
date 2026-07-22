"""Immutable run manifest (write-once)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths
from llm4mtl.serialization.json_io import read_json, write_json


class ManifestExistsError(RuntimeError):
    """Raised when writing a manifest that already exists; manifests are write-once."""


def write_manifest(paths: RunPaths, manifest: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Write the run manifest exactly once. Refuses to overwrite unless ``force``."""
    if paths.manifest.exists() and not force:
        raise ManifestExistsError(f"manifest already exists (write-once): {paths.manifest}")
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, **manifest}
    payload.setdefault("started_at", datetime.now(timezone.utc).isoformat())
    write_json(paths.manifest, payload)
    return payload


def read_manifest(paths: RunPaths) -> dict[str, Any] | None:
    return read_json(paths.manifest) if paths.manifest.exists() else None
