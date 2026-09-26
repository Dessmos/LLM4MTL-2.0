"""Maven execution helpers and Maven project conventions for the generated tests."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# Standard Maven project folders, relative to one module.
MAVEN_TEST_JAVA_DIR = "src/test/java"
MAVEN_TEST_RESOURCES_DIR = "src/test/resources"
# The XML namespace of every element in a Maven POM file.
POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"
# The Surefire option that runs only the named test classes.
TEST_SELECTION_OPTION_PREFIX = "-Dtest="

# The exit code recorded for a command stopped by its timeout. It is the code
# the `timeout` shell tool uses for the same event.
TIMEOUT_EXIT_CODE = 124
# Appended to the standard error of a timed-out command.
TIMEOUT_MARKER = "TIMEOUT"
# Bounds of the one-line error summary.
SUMMARY_MAX_CHARS = 500
SUMMARY_MAX_LINES = 3
SUMMARY_PATTERNS = (
    "COMPILATION ERROR",
    "Failed to execute goal",
    "error:",
    "Failures:",
    "Errors:",
    "Exception",
    "not found",
    "cannot find symbol",
    TIMEOUT_MARKER,
)


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
    """Run ``command`` in ``cwd`` and return its exit code and text output.

    A command that runs longer than ``timeout`` seconds is stopped. That is
    returned as a timed-out result with the output written so far, not raised.
    """
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            exit_code=TIMEOUT_EXIT_CODE,
            stdout=_partial_output(exc.stdout),
            stderr=_partial_output(exc.stderr) + f"\n{TIMEOUT_MARKER}",
            timed_out=True,
        )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _partial_output(output: bytes | str | None) -> str:
    """The output a timed-out command wrote before it was stopped.

    ``TimeoutExpired`` holds bytes here even though ``text=True`` was asked
    for, and ``None`` when the command wrote nothing.
    """
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def summarize_error(output: str) -> str:
    interesting = _interesting_error_lines(output, SUMMARY_PATTERNS)
    if interesting:
        return " | ".join(interesting)[:SUMMARY_MAX_CHARS]

    stripped_output = output.strip()
    if not stripped_output:
        return ""
    return stripped_output.splitlines()[-1][:SUMMARY_MAX_CHARS]


def _interesting_error_lines(
    output: str,
    patterns: tuple[str, ...],
) -> list[str]:
    """Return at most the first three non-empty diagnostic lines."""
    interesting: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern in stripped for pattern in patterns):
            interesting.append(stripped)
        if len(interesting) >= SUMMARY_MAX_LINES:
            break
    return interesting
