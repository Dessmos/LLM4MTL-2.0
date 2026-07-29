"""Immutable normalized LLM-response storage."""

from __future__ import annotations

from typing import Any

from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import write_json


def next_response_attempt(paths: RunPaths, operation: str) -> int:
    """Return the next 1-based response attempt without reusing a directory."""
    operation_dir = paths.response_operation_dir(operation)
    if not operation_dir.is_dir():
        return 1
    numbers = [
        int(item.name.split("-", 1)[1])
        for item in operation_dir.glob("attempt-*")
        if item.is_dir() and item.name.split("-", 1)[1].isdigit()
    ]
    return max(numbers) + 1 if numbers else 1


def record_diagnosis(paths: RunPaths, diagnosis: dict[str, Any]) -> tuple[int, str]:
    """Persist one immutable failure diagnosis and return its attempt and relative path."""
    attempt = next_response_attempt(paths, "failure-diagnosis")
    target = paths.diagnosis_response(attempt)
    write_json(target, diagnosis)
    return attempt, target.relative_to(paths.root).as_posix()
