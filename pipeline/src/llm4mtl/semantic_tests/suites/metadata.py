"""Read the ``metadata.json`` of a candidate suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.domain.observations import ARTIFACT_INVALID_REASON

# The provenance and artifact-validation record inside each candidate suite.
SUITE_METADATA_FILE = "metadata.json"


def artifact_invalid_reason(suite_path: Path) -> str:
    """Why this suite must not be executed, or ``""`` when it may be.

    Fails closed: a suite with no recorded artifact-validation verdict (for
    example from an older extraction) may still contain LLM-written Java, so it
    is refused.
    """
    metadata = _read_suite_metadata(suite_path)
    validation = metadata.get("artifact_validation")
    if not isinstance(validation, dict):
        return (
            "no artifact_validation verdict recorded for this suite; "
            "re-extract it before validation"
        )
    if validation.get("valid") is True:
        return ""
    violations = validation.get("violations") or ["artifact validation failed"]
    reason_code = validation.get("reason_code") or ARTIFACT_INVALID_REASON
    return f"{reason_code}: " + "; ".join(str(item) for item in violations)


def _read_suite_metadata(suite_path: Path) -> dict[str, Any]:
    metadata_path = suite_path / SUITE_METADATA_FILE
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
