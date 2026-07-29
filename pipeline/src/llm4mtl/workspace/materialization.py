"""Atomic materialization of an engine template into an isolated workspace."""

from __future__ import annotations

import fcntl
import os
import shutil
import tempfile
from pathlib import Path


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
    lock_path = workspaces_root / f".{workspace_name}.materialize.lock"
    with lock_path.open("a", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if destination.is_dir():
            return destination
        if destination.exists():
            raise WorkspaceMaterializationError(
                f"workspace destination is not a directory: {destination}"
            )

        temporary_root = Path(
            tempfile.mkdtemp(prefix=f".{workspace_name}-", dir=workspaces_root)
        )
        candidate = temporary_root / "engine"
        try:
            shutil.copytree(
                source,
                candidate,
                ignore=shutil.ignore_patterns("target", ".git", "*.class"),
            )
            os.rename(candidate, destination)
        finally:
            shutil.rmtree(temporary_root, ignore_errors=True)
    return destination
