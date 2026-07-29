"""Immutable normalized LLM-response storage."""

from __future__ import annotations

from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.attempts import claim_attempt
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import write_json


def record_diagnosis(paths: RunPaths, diagnosis: dict[str, Any]) -> tuple[int, str]:
    """Persist one immutable failure diagnosis and return its attempt and relative path."""
    validate_artifact("diagnosis", diagnosis)
    attempt = claim_attempt(
        paths.response_operation_dir("failure-diagnosis"),
        lambda number: paths.response_attempt_dir("failure-diagnosis", number),
    )
    target = paths.diagnosis_response(attempt)
    write_json(target, diagnosis)
    return attempt, target.relative_to(paths.root).as_posix()
