"""Maven execution helpers for the generated-test workflow."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        return f"{self.stdout}\n{self.stderr}".strip()


def run_maven(command: list[str], cwd: Path, timeout: int) -> CommandResult:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            exit_code=124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + "\nTIMEOUT",
            timed_out=True,
        )


def summarize_error(output: str) -> str:
    interesting = []
    patterns = (
        "COMPILATION ERROR",
        "Failed to execute goal",
        "error:",
        "Failures:",
        "Errors:",
        "Exception",
        "not found",
        "cannot find symbol",
        "TIMEOUT",
    )
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern in stripped for pattern in patterns):
            interesting.append(stripped)
        if len(interesting) >= 3:
            break
    if interesting:
        return " | ".join(interesting)[:500]
    return output.strip().splitlines()[-1][:500] if output.strip() else ""
