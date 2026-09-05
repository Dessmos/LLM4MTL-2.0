"""Stable content hashes of the files and directories a run records.

Every artifact identity in the pipeline is a content hash: the run manifest
pins its protected inputs by one, the run store refuses to re-adopt a
transformation whose hash moved, and a failure report re-derives the hashes of
the suite and transformation it describes to prove it is talking about the
execution that actually happened. That makes hashing an I/O boundary shared by
provenance, the run store, prompt assembly, execution, and reporting alike —
not a detail of any one of them.

``directory_sha256`` walks in sorted relative-path order and mixes each path in
with its length before its bytes, so two different directory layouts cannot
collide by concatenation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_BYTES = 1024 * 1024


def file_sha256(path: Path) -> str:
    """The SHA-256 of one file's contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_sha256(path: Path) -> str:
    """The SHA-256 of a directory tree: its relative paths and their contents."""
    digest = hashlib.sha256()
    for child in sorted(
        candidate for candidate in path.rglob("*") if candidate.is_file()
    ):
        relative = child.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with child.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
                digest.update(chunk)
    return digest.hexdigest()
