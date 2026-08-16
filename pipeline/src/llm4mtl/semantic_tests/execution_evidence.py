"""Raw execution evidence, captured before the next ``mvn clean`` destroys it.

Maven writes its Surefire XML into the engine workspace's ``target/`` directory,
and every execution this pipeline performs begins with ``mvn clean``. The reports
describing execution N therefore stop existing the moment execution N+1 starts in
the same workspace, and the workspace is scratch space that no recorded result
may depend on. Source Diagnosis runs after the whole stage has finished, so by
the time it asks what actually happened, the authoritative evidence is already
gone.

This module captures that evidence at the point of execution — while the
workspace lock is still held — and writes it into the run's permanent artifact
tree beside the observation it explains.

Nothing here interprets anything. ``error_summary`` remains the short derived
summary on the observation, the phase classification is unchanged, and a missing
report is recorded as missing rather than filled in with zeros: a count of zero
tests and an unknown number of tests are different facts, and only one of them
can be read off an absent report.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.semantic_tests.surefire import SurefireReport
from llm4mtl.serialization.json_io import write_json

SCHEMA_VERSION = "1.0"

EVIDENCE_DIRNAME = "execution_evidence"
MANIFEST_FILENAME = "evidence.json"
STDOUT_FILENAME = "maven-stdout.log"
STDERR_FILENAME = "maven-stderr.log"
SUREFIRE_DIRNAME = "surefire"


@dataclass(frozen=True)
class SurefireArtifact:
    """One Surefire report file, read verbatim while it still existed."""

    name: str
    content: str


@dataclass(frozen=True)
class RawExecutionEvidence:
    """Everything one Maven invocation produced, held in memory.

    ``reports_present`` is recorded separately from ``reports`` because "the
    directory held no report" and "the reports could not be parsed" are
    different states, and neither may be presented as "the run had no failures".
    ``tests``/``failures``/``errors`` are ``None`` whenever no report parsed.
    """

    exit_code: int | str
    timed_out: bool
    stdout: str
    stderr: str
    reports_present: bool
    reports: tuple[SurefireArtifact, ...] = ()
    tests: int | None = None
    failures: int | None = None
    errors: int | None = None


def capture_execution_evidence(
    result: CommandResult,
    reports_dir: Path,
    report: SurefireReport | None,
) -> RawExecutionEvidence:
    """Read the authoritative evidence of one execution into memory.

    Call this while the workspace lock is still held. Once the reports are read,
    no later ``mvn clean`` can affect what gets persisted.
    """
    files = sorted(reports_dir.glob("TEST-*.xml")) if reports_dir.is_dir() else []
    artifacts = tuple(
        SurefireArtifact(
            name=path.name,
            # Decoding is lenient because a truncated report is still evidence;
            # refusing to read it would discard the only record of the run.
            content=path.read_text(encoding="utf-8", errors="replace"),
        )
        for path in files
    )
    return RawExecutionEvidence(
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        stdout=result.stdout,
        stderr=result.stderr,
        reports_present=bool(artifacts),
        reports=artifacts,
        tests=report.tests if report is not None else None,
        failures=report.failures if report is not None else None,
        errors=report.errors if report is not None else None,
    )


def evidence_dir(observation_path: Path) -> Path:
    """Where the evidence for the observation at ``observation_path`` lives."""
    return observation_path.parent / EVIDENCE_DIRNAME


def write_execution_evidence(
    observation_path: Path,
    evidence: RawExecutionEvidence,
    *,
    suite_identity: dict[str, str],
    inputs: dict[str, dict[str, str]],
    failure_stage: str,
    error_summary: str,
) -> Path:
    """Persist ``evidence`` beside its observation and return the directory.

    The directory is rewritten as a whole so the evidence and the observation it
    explains can never describe different executions.
    """
    directory = evidence_dir(observation_path)
    shutil.rmtree(directory, ignore_errors=True)
    (directory / SUREFIRE_DIRNAME).mkdir(parents=True, exist_ok=True)

    (directory / STDOUT_FILENAME).write_text(evidence.stdout, encoding="utf-8")
    (directory / STDERR_FILENAME).write_text(evidence.stderr, encoding="utf-8")
    for artifact in evidence.reports:
        (directory / SUREFIRE_DIRNAME / artifact.name).write_text(
            artifact.content, encoding="utf-8"
        )

    manifest = _manifest(
        evidence,
        suite_identity=suite_identity,
        inputs=inputs,
        failure_stage=failure_stage,
        error_summary=error_summary,
    )
    validate_artifact("execution-evidence", manifest)
    write_json(directory / MANIFEST_FILENAME, manifest)
    return directory


@dataclass(frozen=True)
class ArchivedEvidence:
    """What the run permanently kept about one execution.

    Empty fields mean the archive holds nothing, which is a fact about the run
    and never a reason to look in the workspace: those files may describe a
    later execution, or may no longer exist.
    """

    directory: Path | None
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None


def archived_execution_evidence(observation_path: Path) -> ArchivedEvidence:
    """Resolve the archived evidence for the observation at ``observation_path``.

    ``execution_log`` is the Maven stdout stream, which carries the reactor
    output, the Surefire summaries, and the ``[ERROR]`` lines. The stderr stream
    is archived beside it and both are named in the manifest.
    """
    directory = evidence_dir(observation_path)
    if not directory.is_dir():
        return ArchivedEvidence(directory=None, surefire_reports=(), execution_log=None)
    reports = directory / SUREFIRE_DIRNAME
    stdout = directory / STDOUT_FILENAME
    return ArchivedEvidence(
        directory=directory,
        surefire_reports=tuple(sorted(reports.glob("TEST-*.xml"))) if reports.is_dir() else (),
        execution_log=stdout if stdout.is_file() else None,
    )


def _manifest(
    evidence: RawExecutionEvidence,
    *,
    suite_identity: dict[str, str],
    inputs: dict[str, dict[str, str]],
    failure_stage: str,
    error_summary: str,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        **suite_identity,
        # The same artifact refs the observation records, so evidence and
        # observation name the same suite and the same transformation in the
        # same role. `role` is what separates a reference execution from a
        # generated-transformation one.
        "inputs": inputs,
        "maven": {
            "exit_code": evidence.exit_code,
            "timed_out": evidence.timed_out,
            "stdout": STDOUT_FILENAME,
            "stderr": STDERR_FILENAME,
            "stdout_bytes": len(evidence.stdout.encode("utf-8")),
            "stderr_bytes": len(evidence.stderr.encode("utf-8")),
        },
        "surefire": {
            "present": evidence.reports_present,
            "directory": SUREFIRE_DIRNAME,
            "reports": [artifact.name for artifact in evidence.reports],
            "tests": evidence.tests,
            "failures": evidence.failures,
            "errors": evidence.errors,
        },
        # Copied from the observation so the evidence is self-describing. It is
        # a record of the verdict, never an input to it.
        "classification": {
            "failure_stage": failure_stage,
            "error_summary": error_summary,
        },
    }
