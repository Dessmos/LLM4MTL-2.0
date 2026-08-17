"""Shared subprocess and selection helpers for adapters."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from llm4mtl.experiment_runner.config import ConfigError


def _path_hash_chunks(path: Path) -> Iterator[bytes]:
    name = str(path).encode("utf-8")
    yield len(name).to_bytes(8, "big")
    yield name
    if path.is_file():
        yield path.read_bytes()
        return
    if not path.is_dir():
        return

    files = sorted(candidate for candidate in path.rglob("*") if candidate.is_file())
    for child in files:
        yield str(child.relative_to(path)).encode("utf-8")
        yield child.read_bytes()


def hash_paths(paths: list[Path]) -> str:
    """Hash selected files and directory contents in deterministic path order."""
    digest = hashlib.sha256()
    for path in sorted({item.resolve() for item in paths}):
        for chunk in _path_hash_chunks(path):
            digest.update(chunk)
    return digest.hexdigest()


def fixed_selection(axis: str, values: list[str]) -> set[str]:
    """The values a stage may select for one identity axis.

    Never falls back to "every known value": a stage that selected the whole
    matrix would produce results attributed to a run whose identity names one
    combination.
    """
    if not values:
        raise ConfigError(
            f"this stage needs the run's {axis}, but the run fixed none. "
            "Select it explicitly instead of running against every value."
        )
    return set(values)
