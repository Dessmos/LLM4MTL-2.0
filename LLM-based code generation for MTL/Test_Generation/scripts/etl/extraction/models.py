"""Data structures and constants for generated-suite extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.paths import LANGUAGE_ETL


LANGUAGE = LANGUAGE_ETL
ALLOWED_EXTENSIONS = {".java", ".model", ".xmi", ".xml"}


@dataclass(frozen=True)
class Block:
    info: str
    content: str
    start: int


@dataclass(frozen=True)
class ResponseTarget:
    response_path: Path
    llm: str
    strategy: str
    task: str
