"""Per-stage result store: immutable attempts + a mutable ``latest.json`` projection."""

from __future__ import annotations

from typing import Any

from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import read_json, write_json


def next_attempt(paths: RunPaths, stage: str) -> int:
    """The next 1-based attempt number for ``stage`` (never reuses an existing one)."""
    attempts_dir = paths.stage_attempts_dir(stage)
    if not attempts_dir.is_dir():
        return 1
    numbers = [
        int(item.name.split("-", 1)[1])
        for item in attempts_dir.glob("attempt-*")
        if item.is_dir() and item.name.split("-", 1)[1].isdigit()
    ]
    return max(numbers) + 1 if numbers else 1


def record_attempt(paths: RunPaths, stage: str, result: dict[str, Any]) -> int:
    """Persist an immutable attempt and refresh ``latest.json``; returns the attempt number."""
    attempt = next_attempt(paths, stage)
    payload = {**result, "attempt": attempt}
    write_json(paths.stage_attempt_result(stage, attempt), payload)  # immutable evidence
    write_json(paths.stage_latest(stage), payload)  # mutable projection read by n8n
    return attempt


def read_latest(paths: RunPaths, stage: str) -> dict[str, Any] | None:
    path = paths.stage_latest(stage)
    return read_json(path) if path.exists() else None


def list_stages(paths: RunPaths) -> list[str]:
    if not paths.stages_dir.is_dir():
        return []
    return sorted(item.name for item in paths.stages_dir.iterdir() if item.is_dir())
