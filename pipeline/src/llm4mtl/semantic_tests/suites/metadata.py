"""Shared reading of per-suite metadata across validation stages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_suite_metadata(suite_path: Path) -> dict[str, Any]:
    metadata_path = suite_path / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def artifact_invalid_reason(suite_path: Path) -> str:
    """Why this suite must not be executed, or ``""`` when it may be.

    Fails closed: a suite whose extraction did not record an artifact-validation
    verdict predates the current policy and may still contain LLM-authored Java,
    so it is refused rather than trusted.
    """
    metadata = read_suite_metadata(suite_path)
    validation = metadata.get("artifact_validation")
    if not isinstance(validation, dict):
        return (
            "no artifact_validation verdict recorded for this suite; "
            "re-extract it before validation"
        )
    if validation.get("valid") is True:
        return ""
    violations = validation.get("violations") or ["artifact validation failed"]
    reason_code = validation.get("reason_code") or "ARTIFACT_INVALID"
    return f"{reason_code}: " + "; ".join(str(item) for item in violations)
