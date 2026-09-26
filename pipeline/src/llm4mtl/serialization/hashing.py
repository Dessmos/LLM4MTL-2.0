"""Stable content hashes of the files and directories a run records.

The pipeline identifies artifacts by content hash. Provenance pins protected
inputs with them, the run store checks stored transformations with them, and
failure reports use them to prove which suite and transformation they describe.
Many packages need the same hashes, so they live here.

``directory_sha256`` walks files in sorted relative-path order. It writes each
path's length before the path, so two different layouts cannot produce the same
byte stream.
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
