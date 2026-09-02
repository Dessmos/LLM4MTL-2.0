"""Resolve a response's fenced blocks to the artifacts it actually declared.

Extraction reads what the response says. It does not work out what the response
probably meant.

That distinction is an RQ1 measurement boundary. The extract stage is the first
gate of the validation funnel, so a parser that recovers a file name from
surrounding prose, keeps the first of two blocks claiming the same file, or
files an unrecognized artifact under ``models/`` is answering the research
question on the model's behalf. The prompt contract asks for named file blocks
and nothing else:

    The generated response must contain semantic test artifacts only:
    - one semantic_cases.json file block,
    - one or more generated source model file blocks,
    - no Java, no JUnit, no Maven files, and no prose outside file blocks.

So every block must name its own file, in its own info string:

    ```json file=semantic_cases.json
    ```xml file=models/input.model

Anything else raises :class:`ExtractionError`. The extract stage records the
response as a failed extraction and keeps going — the workflow survives, the
candidate stays in the denominator, and the failure is attributed to the
response that caused it.
"""

from __future__ import annotations

import re
from pathlib import Path

from llm4mtl.semantic_tests.extraction.models import (
    ALLOWED_EXTENSIONS,
    Block,
    ExtractionError,
)

# `file=`, `filename=`, or `path=` inside the fence's info string.
DECLARED_PATH = re.compile(
    r"(?:^|\s)(?:file|filename|path)\s*=\s*[\"']?([^\"'\s`{}]+)",
    re.IGNORECASE,
)

MODEL_EXTENSIONS = {".model", ".xmi", ".xml"}
MODELS_DIRECTORY = "models"


def parse_fenced_blocks(markdown: str) -> list[Block]:
    """Return fenced blocks in their source order."""
    pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
    return [
        Block(
            info=match.group(1).strip(),
            content=clean_content(match.group(2)),
            start=match.start(),
        )
        for match in pattern.finditer(markdown)
    ]


def clean_content(text: str) -> str:
    """Normalize a block to one trailing newline."""
    return text.rstrip() + "\n"


def extract_files(markdown: str) -> dict[str, str]:
    """The artifacts this response declared, keyed by their canonical path.

    Raises :class:`ExtractionError` when a block does not name its file, names
    one whose role the contract does not define, or repeats an identity another
    block already claimed. A response containing no fenced block at all yields
    an empty result, which the caller already reports as nothing to extract.
    """
    extracted: dict[str, str] = {}
    for index, block in enumerate(parse_fenced_blocks(markdown), start=1):
        declared = declared_file_path(block)
        if declared is None:
            raise ExtractionError(
                f"block #{index} (```{block.info}) does not name a file. Every "
                "block must declare its own path, for example "
                "```json file=semantic_cases.json"
            )
        path = canonical_generated_path(declared, block_index=index)
        if path in extracted:
            raise ExtractionError(
                f"block #{index} claims the artifact {path!r}, which an earlier "
                "block already declared. Each artifact must be emitted once."
            )
        extracted[path] = block.content
    return extracted


def declared_file_path(block: Block) -> str | None:
    """The path this block states for itself, or ``None`` when it states none.

    Only the block's own info string is consulted. Reading the prose before a
    block is how an illustrative snippet became a generated artifact.
    """
    match = DECLARED_PATH.search(block.info)
    if match:
        return match.group(1)

    # A bare info string that is itself a file name, e.g. ```semantic_cases.json
    first = block.info.split()[0] if block.info.split() else ""
    if Path(first.strip()).suffix.lower() in ALLOWED_EXTENSIONS:
        return first

    return None


def canonical_generated_path(declared: str, *, block_index: int) -> str:
    """Canonicalize a declared path, or refuse a role the contract does not define."""
    cleaned = declared.strip().replace("\\", "/").lstrip("/")
    path = Path(cleaned)
    if path.is_absolute() or ".." in path.parts:
        raise ExtractionError(
            f"block #{block_index} declares {declared!r}, which escapes the "
            "suite directory"
        )

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ExtractionError(
            f"block #{block_index} declares {declared!r}, whose role the contract "
            f"does not define. Generated artifacts use: {allowed}"
        )

    if suffix in {".java", ".json"}:
        return path.name

    if path.parts[:1] == (MODELS_DIRECTORY,):
        return str(path)

    raise ExtractionError(
        f"block #{block_index} declares the model file {declared!r} outside "
        f"{MODELS_DIRECTORY}/. Generated model files belong under "
        f"{MODELS_DIRECTORY}/, as the paths in semantic_cases.json reference them."
    )


def java_files(extracted: dict[str, str]) -> list[str]:
    """Return generated Java artifact paths in deterministic order."""
    return sorted(path for path in extracted if path.endswith(".java"))


def model_files(extracted: dict[str, str]) -> list[str]:
    """Return generated model artifact paths in deterministic order."""
    return sorted(
        path for path in extracted if path.endswith((".model", ".xmi", ".xml"))
    )


def semantic_case_files(extracted: dict[str, str]) -> list[str]:
    """Return semantic-case JSON artifact paths in deterministic order."""
    return sorted(path for path in extracted if path.endswith(".json"))
