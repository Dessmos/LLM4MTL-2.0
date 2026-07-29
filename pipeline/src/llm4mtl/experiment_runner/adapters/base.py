"""Shared subprocess and selection helpers for adapters."""

from __future__ import annotations

import hashlib
from pathlib import Path

from llm4mtl.experiment_runner.config import ConfigError


def hash_paths(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted({item.resolve() for item in paths}):
        name = str(path).encode("utf-8")
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        if path.is_file():
            digest.update(path.read_bytes())
        elif path.is_dir():
            for child in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
                relative = str(child.relative_to(path)).encode("utf-8")
                digest.update(relative)
                digest.update(child.read_bytes())
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
