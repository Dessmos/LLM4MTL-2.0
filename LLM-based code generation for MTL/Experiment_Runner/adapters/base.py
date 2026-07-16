"""Shared subprocess and selection helpers for adapters."""

from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandExecution:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def run_command(command: list[str], cwd: Path, verbose: bool) -> CommandExecution:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if verbose:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr, end="" if completed.stdout.endswith("\n") else "\n")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    return CommandExecution(command, completed.returncode, completed.stdout, completed.stderr)


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


def python_command(script: Path) -> list[str]:
    return [sys.executable, str(script)]
