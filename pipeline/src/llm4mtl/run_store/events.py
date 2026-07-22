"""Append-only run event log (``events.jsonl``)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths


def append_event(
    paths: RunPaths,
    event: str,
    *,
    stage: str | None = None,
    outcome_code: str | None = None,
    status: str | None = None,
    attempt: int | None = None,
) -> dict[str, Any]:
    """Append one immutable event line; returns the written record."""
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
    }
    if stage is not None:
        record["stage"] = stage
    if status is not None:
        record["status"] = status
    if outcome_code is not None:
        record["outcome_code"] = outcome_code
    if attempt is not None:
        record["attempt"] = attempt
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    with paths.events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_events(paths: RunPaths) -> list[dict[str, Any]]:
    if not paths.events.exists():
        return []
    return [
        json.loads(line)
        for line in paths.events.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
