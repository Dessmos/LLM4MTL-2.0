"""Markdown fenced-block parsing for generated suite artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from etl.extraction.models import ALLOWED_EXTENSIONS, Block


def parse_fenced_blocks(markdown: str) -> list[Block]:
    pattern = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
    return [
        Block(info=match.group(1).strip(), content=clean_content(match.group(2)), start=match.start())
        for match in pattern.finditer(markdown)
    ]


def clean_content(text: str) -> str:
    return text.rstrip() + "\n"


def extract_files(markdown: str) -> dict[str, str]:
    blocks = parse_fenced_blocks(markdown)
    extracted: dict[str, str] = {}

    for block in blocks:
        raw_path = infer_file_path(block, markdown)
        if not raw_path:
            continue
        normalized = normalize_generated_path(raw_path)
        if not normalized:
            continue
        extracted.setdefault(normalized, block.content)

    return extracted


def infer_file_path(block: Block, markdown: str) -> str | None:
    from_info = file_path_from_info(block.info)
    if from_info:
        return from_info

    prefix = markdown[max(0, block.start - 400) : block.start]
    return file_path_from_nearby_text(prefix)


def file_path_from_info(info: str) -> str | None:
    match = re.search(
        r"(?:^|\s)(?:file|filename|path)\s*=\s*[\"']?([^\"'\s`{}]+)",
        info,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    first = info.split()[0] if info.split() else ""
    if looks_like_extractable_file(first):
        return first

    return None


def file_path_from_nearby_text(text: str) -> str | None:
    match = re.search(
        r"(?:file|filename|path)\s*[:=]\s*[`\"']?([^`\"'\s]+)",
        text,
        re.IGNORECASE,
    )
    if match and looks_like_extractable_file(match.group(1)):
        return match.group(1)

    match = re.search(r"([A-Za-z0-9_./-]+\.(?:java|model|xmi|xml))", text)
    if match:
        return match.group(1)

    return None


def looks_like_extractable_file(value: str) -> bool:
    return Path(value.strip()).suffix.lower() in ALLOWED_EXTENSIONS


def normalize_generated_path(path_value: str) -> str | None:
    cleaned = path_value.strip().replace("\\", "/").lstrip("/")
    path = Path(cleaned)
    if path.is_absolute() or ".." in path.parts:
        return None

    suffix = path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return None

    if suffix == ".java":
        return path.name

    if path.parts and path.parts[0] == "models":
        return str(path)

    return f"models/{path.name}"


def java_files(extracted: dict[str, str]) -> list[str]:
    return sorted(path for path in extracted if path.endswith(".java"))


def model_files(extracted: dict[str, str]) -> list[str]:
    return sorted(path for path in extracted if path.endswith((".model", ".xmi", ".xml")))
