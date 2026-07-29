"""Append-only run event log (``events.jsonl``).

``status`` carries the stage vocabulary (passed / failed / skipped /
infrastructure_error) and ``run_status`` the run vocabulary. They are separate
fields because they are separate vocabularies: folding a run outcome into a
stage status is exactly how a skipped stage starts reading as a passed one.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.models import SCHEMA_VERSION, RunPaths


def append_event(
    paths: RunPaths,
    event: str,
    *,
    stage: str | None = None,
    outcome_code: str | None = None,
    status: str | None = None,
    run_status: str | None = None,
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
    if run_status is not None:
        record["run_status"] = run_status
    if outcome_code is not None:
        record["outcome_code"] = outcome_code
    if attempt is not None:
        record["attempt"] = attempt
    validate_artifact("events", record)
    paths.events.parent.mkdir(parents=True, exist_ok=True)
    with paths.events.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def read_events(paths: RunPaths) -> list[dict[str, Any]]:
    if not paths.events.exists():
        return []
    with paths.events.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        content = handle.read()
    records = [json.loads(line) for line in content.splitlines() if line.strip()]
    for record in records:
        validate_artifact("events", record)
    return records
