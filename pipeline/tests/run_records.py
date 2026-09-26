"""Read what a run wrote, for tests only.

The pipeline itself never reads these files back, so the readers live here and
not in the package.
"""

from __future__ import annotations

import json
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.results import result_path


def read_events(paths: RunPaths) -> list[dict[str, Any]]:
    """Every event of the run, in order, each checked against its schema."""
    if not paths.events.exists():
        return []
    lines = paths.events.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    for event in events:
        validate_artifact("events", event)
    return events


def read_result(paths: RunPaths) -> dict[str, Any] | None:
    """The run's final result, or None while the run has not ended."""
    path = result_path(paths)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
