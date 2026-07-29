"""Interpret Maven output for reference validation result fields."""

from __future__ import annotations

from llm4mtl.external_tools.maven import CommandResult


COMPILE_MARKERS = (
    "COMPILATION ERROR",
    "Compilation failure",
    "cannot find symbol",
    "package does not exist",
    "Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin",
)

NO_TEST_MARKERS = (
    "No tests matching pattern",
    "No tests were executed",
    "No tests to run",
)

TEST_EXECUTION_MARKERS = (
    "Tests run:",
    "Failures:",
    "Errors:",
    "Surefire report",
)

# The transformation engine rejected the transformation itself. Against a
# generated transformation that is a defect under test; against the trusted
# reference it means the harness is broken, so it is never an oracle verdict.
TRANSFORMATION_PARSE_MARKERS = (
    "ETL parse errors",
    "ParseProblem",
)


def compiles(result: CommandResult) -> bool:
    return not contains_any(result.output, COMPILE_MARKERS)


def executes(result: CommandResult) -> bool:
    if result.timed_out:
        return False
    if contains_any(result.output, NO_TEST_MARKERS):
        return False
    return result.exit_code == 0 or contains_any(result.output, TEST_EXECUTION_MARKERS)


def transformation_parse_failed(output: str) -> bool:
    return contains_any(output, TRANSFORMATION_PARSE_MARKERS)


def contains_any(output: str, markers: tuple[str, ...]) -> bool:
    return any(marker in output for marker in markers)
