"""Temporarily write files into a workspace, then put the old files back."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


class Injection:
    """Records every file it writes so that ``restore`` can undo them all.

    Call ``restore`` (normally in a ``finally`` block) to put back the original
    files and delete the files that did not exist before.
    """

    def __init__(self) -> None:
        self._backup_dir = Path(tempfile.mkdtemp(prefix="generated-suite-backup-"))
        self._backups: dict[Path, Path | None] = {}

    def write_text(self, destination: Path, content: str) -> None:
        self._backup(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")

    def copy_file(self, source: Path, destination: Path) -> None:
        self._backup(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _backup(self, destination: Path) -> None:
        destination = destination.resolve()
        if destination in self._backups:
            return
        if destination.exists():
            backup = self._backup_dir / f"{len(self._backups)}.bak"
            shutil.copy2(destination, backup)
            self._backups[destination] = backup
        else:
            self._backups[destination] = None

    def restore(self) -> None:
        for destination, backup in reversed(list(self._backups.items())):
            if backup is None:
                destination.unlink(missing_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup, destination)
        shutil.rmtree(self._backup_dir, ignore_errors=True)
