"""Shared data structures for generated suite workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CandidateSuite:
    path: Path
    task: str
    llm: str
    strategy: str
    suite_id: str
