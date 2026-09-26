"""Data structures and constants for generated-suite extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from llm4mtl.task_contracts.models import MODEL_FILE_SUFFIXES

ALLOWED_EXTENSIONS = {".java", ".json", *MODEL_FILE_SUFFIXES}


class ExtractionError(ValueError):
    """A response's file blocks do not resolve to one unambiguous artifact set.

    Raised instead of quietly repairing the response: a block whose file name
    has to be guessed, an artifact identity claimed twice, or a file whose role
    the contract does not define are all defects in the generated output, and
    the extract stage must report them as such rather than produce a suite the
    response did not actually specify.
    """


class ResponseSelectionError(ValueError):
    """A response cannot be attributed to exactly one task, model, and strategy.

    Raised before anything is written: without an unambiguous identity the
    candidate would be filed under a combination the response never belonged to.
    """


class SuiteExistsError(FileExistsError):
    """The candidate directory a response would be written to already exists.

    Candidates are immutable scientific evidence, so a second extraction into
    the same suite id is refused rather than merged or overwritten.
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


@dataclass(frozen=True)
class ExtractionOptions:
    """Where extracted candidates are written, and whether anything is written.

    ``suite_id`` names the candidate explicitly; ``None`` allocates the next
    free ``suite_NNN`` below the response's strategy directory.
    """

    generated_tests_root: Path
    suite_id: str | None = None
    dry_run: bool = False
