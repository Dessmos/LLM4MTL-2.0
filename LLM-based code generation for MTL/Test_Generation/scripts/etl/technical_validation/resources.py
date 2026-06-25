"""Generated model/resource validation helpers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path


def check_models_load(model_paths: list[Path]) -> tuple[bool, str]:
    for path in model_paths:
        if path.suffix.lower() not in {".model", ".xmi", ".xml"}:
            continue
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            return False, f"XML parse failed for {path.name}: {exc}"
    return True, ""
