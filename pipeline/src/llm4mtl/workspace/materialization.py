"""Atomic materialization of an engine template into an isolated workspace."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Build output and repository metadata are not part of the engine template.
IGNORED_TEMPLATE_ENTRIES = ("target", ".git", "*.class")


class WorkspaceMaterializationError(RuntimeError):
    """Raised when an engine template cannot become an isolated workspace."""


def materialize_engine(
    source: Path,
    workspaces_root: Path,
    workspace_name: str,
) -> Path:
    """Return one complete workspace copied from the read-only engine template.

    Concurrent callers share the finished copy, but never observe a partial
    directory. The source is only read, so a crash cannot leave the repository's
    shared harness injected or otherwise modified.
    """
    source = Path(source).resolve()
    if not source.is_dir():
        raise WorkspaceMaterializationError(
            f"engine template directory not found: {source}"
        )
    if not workspace_name or Path(workspace_name).name != workspace_name:
        raise WorkspaceMaterializationError(
            f"workspace name must be one path component: {workspace_name!r}"
        )

    workspaces_root = Path(workspaces_root).resolve()
    workspaces_root.mkdir(parents=True, exist_ok=True)
    destination = workspaces_root / workspace_name
    with _exclusive_lock(workspaces_root / f".{workspace_name}.materialize.lock"):
        if destination.is_dir():
            return destination
        if destination.exists():
            raise WorkspaceMaterializationError(
                f"workspace destination is not a directory: {destination}"
            )
        _copy_then_rename(source, destination)
    return destination


@contextmanager
def _exclusive_lock(lock_path: Path) -> Iterator[None]:
    """Hold an exclusive lock on ``lock_path`` for the duration of the block."""
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def _copy_then_rename(source: Path, destination: Path) -> None:
    """Copy ``source`` beside ``destination``, then rename it into place.

    The rename is atomic, so ``destination`` is either absent or complete.
    """
    temporary_root = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent)
    )
    candidate = temporary_root / "engine"
    try:
        shutil.copytree(
            source,
            candidate,
            ignore=shutil.ignore_patterns(*IGNORED_TEMPLATE_ENTRIES),
        )
        os.rename(candidate, destination)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)
