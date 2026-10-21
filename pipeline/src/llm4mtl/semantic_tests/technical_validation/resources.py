"""Check that a suite's generated model files are well-formed XML."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from llm4mtl.task_contracts.models import MODEL_FILE_SUFFIXES


def check_models_load(model_paths: list[Path]) -> tuple[bool, str]:
    for path in model_paths:
        if path.suffix.lower() not in MODEL_FILE_SUFFIXES:
            continue
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            return False, f"XML parse failed for {path.name}: {exc}"
    return True, ""
