"""Data structures and constants for generated-suite extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_EXTENSIONS = {".java", ".json", ".model", ".xmi", ".xml"}


class ExtractionError(ValueError):
    """A response's file blocks do not resolve to one unambiguous artifact set.

    Raised instead of quietly repairing the response: a block whose file name
    has to be guessed, an artifact identity claimed twice, or a file whose role
    the contract does not define are all defects in the generated output, and
    the extract stage must report them as such rather than produce a suite the
    response did not actually specify.
    """


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
