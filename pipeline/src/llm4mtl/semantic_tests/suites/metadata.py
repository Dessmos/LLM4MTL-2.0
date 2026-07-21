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


def contract_invalid_reason(suite_path: Path) -> str:
    """Return a violation summary when the suite failed contract enforcement."""
    metadata = read_suite_metadata(suite_path)
    enforcement = metadata.get("contract_enforcement") or {}
    if metadata.get("status") == "invalid" or enforcement.get("valid") is False:
        violations = enforcement.get("violations") or ["contract enforcement failed"]
        return "contract violation: " + "; ".join(str(item) for item in violations)
    return ""
