"""One execution of a generated suite, observed as several independent facts.

Running a generated suite answers two different questions at once, and the
pipeline must not confuse them:

* *technical executability* — did the rendered harness compile, were the tests
  discovered, did the models load, did the transformation engine run at all?
* *oracle validity* — given that it ran against the trusted reference
  transformation, do the generated assertions hold?

A suite whose assertions fail has answered the first question with yes and the
second with no. Treating that as a technical failure silently removes wrong
oracles from the reference-pass population and understates the executability
rate, which corrupts every rate derived from the funnel.

Both questions therefore come from ONE Maven run against the reference
transformation. The observation is recorded so a later stage can classify from
it instead of executing again.
"""

from __future__ import annotations

import fcntl
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.domain import ArtifactRef, GeneratedSuite, SuiteExecutionObservation
from llm4mtl.external_tools.maven import CommandResult, run_maven, summarize_error
from llm4mtl.paths import repository_relative
from llm4mtl.semantic_tests.reference_validation.maven_status import (
    compiles,
    executes,
    transformation_parse_failed,
)
from llm4mtl.semantic_tests.execution_evidence import (
    RawExecutionEvidence,
    capture_execution_evidence,
    write_execution_evidence,
)
from llm4mtl.semantic_tests.suites.injection import inject_suite
from llm4mtl.semantic_tests.suites.java import infer_fqcn
from llm4mtl.semantic_tests.surefire import (
    UNCLASSIFIED_RUNTIME,
    SurefireReport,
    read_surefire_reports,
)
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.transformation_execution.hashing import directory_sha256, file_sha256
from llm4mtl.workspace.injection import Injection

SCHEMA_VERSION = "2.0"
OBSERVATION_FILENAME = "suite_execution.json"
REFERENCE_TRANSFORMATION_ROLE = "reference_transformation"
GENERATED_TRANSFORMATION_ROLE = "generated_transformation"
TransformationRole = Literal[
    "reference_transformation",
    "generated_transformation",
]


@dataclass(frozen=True)
class _ConsoleTestCounts:
    """Test totals parsed from Maven's last Surefire summary line."""

    tests: int
    failures: int
    errors: int


def classify_maven_run(
    result: CommandResult,
    reports: SurefireReport | None = None,
) -> SuiteExecutionObservation:
    """Derive the independent observations from one Maven invocation.

    Maven's console output cannot tell the harness phases apart: a model that
    failed to load, an engine that threw, and an assertion that did not hold all
    print as ``Tests run: N, Failures: F, Errors: E``. Treating them alike marks
    a broken test as technically executable and its breakage as a disagreement
    with the reference — inflating executability and corrupting the reference-pass
    population. The Surefire reports do distinguish them, so they decide the
    phases whenever they exist; the console is only a fallback for runs that
    never produced reports (a compile failure, a timeout).
    """
    did_compile = compiles(result)
    if result.timed_out:
        return _phase_failure(result, "timeout", compiled=did_compile)
    if not did_compile:
        return _phase_failure(result, "java_compilation", compiled=False)

    # Only the total absence of readable XML may fall back to the console. A
    # report that parsed and counted zero tests is evidence that nothing ran,
    # and `_classify_from_reports` turns it into a test-discovery failure.
    if reports is None:
        return _classify_from_console(result, did_compile)
    return _classify_from_reports(result, reports)


def _classify_from_reports(
    result: CommandResult, reports: SurefireReport
) -> SuiteExecutionObservation:
    if reports.tests == 0:
        return _phase_failure(result, "test_discovery", compiled=True)

    failure_stage = reports.failure_stage()
    if failure_stage in {
        "model_loading",
        "transformation_parse",
        "engine_runtime",
        UNCLASSIFIED_RUNTIME,
    }:
        # The harness never got far enough to judge the oracle.
        return SuiteExecutionObservation(
            compiled=True,
            tests_discovered=True,
            models_loaded=failure_stage in {"transformation_parse", "engine_runtime"},
            engine_started=failure_stage == "engine_runtime",
            assertions_evaluated=False,
            assertions_passed=False,
            timed_out=False,
            maven_exit_code=result.exit_code,
            failure_stage=failure_stage,
            error_summary=reports.first_error or summarize_error(result.output),
        )

    assertions_passed = reports.failures == 0 and reports.errors == 0
    return SuiteExecutionObservation(
        compiled=True,
        tests_discovered=True,
        models_loaded=True,
        engine_started=True,
        assertions_evaluated=True,
        assertions_passed=assertions_passed,
        timed_out=False,
        maven_exit_code=result.exit_code,
        failure_stage="" if assertions_passed else "assertion_failure",
        error_summary=(
            ""
            if assertions_passed
            else reports.first_failure or summarize_error(result.output)
        ),
    )


def _classify_from_console(
    result: CommandResult,
    did_compile: bool,
) -> SuiteExecutionObservation:
    """Fallback when no Surefire report exists: only coarse phases are knowable."""
    if transformation_parse_failed(result.output):
        return _phase_failure(result, "transformation_parse", compiled=True)
    if not executes(result):
        return _phase_failure(result, "test_discovery", compiled=did_compile)

    counts = _console_test_counts(result.output)
    if counts is None or counts.tests == 0:
        # No XML, and no "Tests run: N" line saying a test ran. An exit code of
        # 0 in that state is not evidence of a passing suite: it is what
        # `-Dsurefire.failIfNoSpecifiedTests=false` produces when the selector
        # matched nothing, and treating it as success would validate a suite
        # that never executed.
        return _phase_failure(result, "test_discovery", compiled=True)
    if counts.errors > 0:
        # Console summaries distinguish JUnit errors from assertion failures but
        # do not identify which harness phase threw. Without XML, naming a phase
        # would invent evidence.
        return _phase_failure(
            result, UNCLASSIFIED_RUNTIME, compiled=True, tests_discovered=True
        )
    if result.exit_code != 0 and counts.failures == 0:
        return _phase_failure(
            result, UNCLASSIFIED_RUNTIME, compiled=True, tests_discovered=True
        )

    assertions_passed = (
        result.exit_code == 0 and counts.failures == 0 and counts.errors == 0
    )
    return SuiteExecutionObservation(
        compiled=True,
        tests_discovered=True,
        models_loaded=True,
        engine_started=True,
        assertions_evaluated=True,
        assertions_passed=assertions_passed,
        timed_out=False,
        maven_exit_code=result.exit_code,
        failure_stage="" if assertions_passed else "assertion_failure",
        error_summary="" if assertions_passed else summarize_error(result.output),
    )


SUREFIRE_SUMMARY = re.compile(
    r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)",
    re.IGNORECASE,
)


def _console_test_counts(output: str) -> _ConsoleTestCounts | None:
    matches = list(SUREFIRE_SUMMARY.finditer(output))
    if not matches:
        return None
    tests, failures, errors = matches[-1].groups()
    return _ConsoleTestCounts(
        tests=int(tests),
        failures=int(failures),
        errors=int(errors),
    )


def _phase_failure(
    result: CommandResult,
    failure_stage: str,
    *,
    compiled: bool,
    tests_discovered: bool = False,
) -> SuiteExecutionObservation:
    return SuiteExecutionObservation(
        compiled=compiled,
        tests_discovered=tests_discovered,
        models_loaded=False,
        engine_started=False,
        assertions_evaluated=False,
        assertions_passed=False,
        timed_out=failure_stage == "timeout",
        maven_exit_code=result.exit_code,
        failure_stage=failure_stage,
        error_summary=summarize_error(result.output),
    )


def execute_suite_against(
    suite: GeneratedSuite,
    transformation: Path,
    test_project_dir: Path,
    timeout: int,
    observations_root: Path | None = None,
) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
    """Run one rendered suite against ``transformation`` and observe the outcome.

    The transformation is always injected explicitly: executability is only
    meaningful relative to a known transformation, and the harness ships its own
    copies that would otherwise be used silently.

    ``observations_root`` is where the harness writes the actual target models it
    produced. Omitting it means this execution keeps no snapshot — which is a
    caller's decision, never a silent default.

    Returns the observation and the raw evidence behind it. The evidence is read
    while the workspace lock is still held, because the next execution's
    ``mvn clean`` deletes the reports this one produced.
    """
    java_paths, model_paths = _suite_artifact_paths(suite)

    # A run can receive concurrent stage requests. The run-local workspace keeps
    # separate runs apart; this lock keeps two executions within the same run
    # from injecting into that workspace at once.
    with execution_workspace_lock(test_project_dir):
        injection = Injection()
        try:
            injection.copy_file(
                transformation,
                _transformation_destination(test_project_dir, suite.task),
            )
            inject_suite(suite, java_paths, model_paths, test_project_dir, injection)
            command = _maven_command(java_paths, observations_root, suite)
            result = run_maven(command, cwd=test_project_dir, timeout=timeout)
            # `mvn clean` wipes target/ first, so these reports describe this run only.
            reports_root = test_project_dir / "target" / "surefire-reports"
            reports = read_surefire_reports(reports_root)
            evidence = capture_execution_evidence(result, reports_root, reports)
        finally:
            injection.restore()

    return classify_maven_run(result, reports), evidence


def _suite_artifact_paths(suite: GeneratedSuite) -> tuple[list[Path], list[Path]]:
    """Return deterministic Java and model input paths for ``suite``."""
    java_paths = sorted(suite.path.glob("*.java"))
    model_paths = sorted(
        path for path in (suite.path / "models").rglob("*") if path.is_file()
    )
    return java_paths, model_paths


def _maven_command(
    java_paths: list[Path],
    observations_root: Path | None,
    suite: GeneratedSuite,
) -> list[str]:
    """Build the Maven command for one suite execution."""
    selector = ",".join(infer_fqcn(path) for path in java_paths)
    command = ["mvn", "clean", "test", f"-Dtest={selector}"]
    if observations_root is not None:
        observations_dir = snapshot_dir(observations_root, suite)
        command.append(f"-Dllm4mtl.observations.dir={observations_dir}")
    return command


@contextmanager
def execution_workspace_lock(test_project_dir: Path) -> Iterator[None]:
    """Serialize mutations of one materialized harness workspace."""
    lock_path = test_project_dir / ".llm4mtl-execution.lock"
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _transformation_destination(test_project_dir: Path, task: str) -> Path:
    from llm4mtl.semantic_tests.reference_validation.reference import (
        transformation_destination,
    )

    return transformation_destination(test_project_dir, task)


def observation_path(observations_root: Path, suite: GeneratedSuite) -> Path:
    """Where the observation for ``suite`` is recorded within one run."""
    return (
        observations_root
        / suite.task
        / suite.llm
        / suite.strategy
        / suite.suite_id
        / OBSERVATION_FILENAME
    )


def snapshot_dir(observations_root: Path, suite: GeneratedSuite) -> Path:
    """Where ``suite``'s actual output models are written, for one execution.

    Scoped to the observation, not to the transformation. A snapshot's identity
    is transformation + suite + test case + model slot, and the first three are
    all in this path (the case is a directory the harness creates below it).
    Sharing one directory per transformation let two suites with the same case
    name overwrite each other's actual output — and a diagnosis assembled from
    the survivor would describe a failure that never produced it.
    """
    return observation_path(observations_root, suite).parent / "snapshots"


@contextmanager
def observation_lock(
    observations_root: Path,
    suite: GeneratedSuite,
) -> Iterator[None]:
    """Serialize observation creation for one suite across threads/processes."""
    path = observation_path(observations_root, suite)
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def record_observation(
    observations_root: Path,
    suite: GeneratedSuite,
    transformation: Path,
    observation: SuiteExecutionObservation,
    *,
    transformation_role: TransformationRole = REFERENCE_TRANSFORMATION_ROLE,
    evidence: RawExecutionEvidence | None = None,
) -> Path:
    """Persist an observation together with the inputs it was derived from.

    Validated on write: the funnel's denominators are derived from these records,
    so a malformed one would corrupt a metric rather than fail a stage.

    When ``evidence`` is supplied it is archived beside the observation in the
    same call, so the run's permanent artifacts hold the complete Maven output
    and Surefire reports this observation was derived from. That has to happen
    here rather than at the end of the stage: the workspace those reports live
    in is wiped by the next execution's ``mvn clean``.
    """
    path = observation_path(observations_root, suite)
    identity = _suite_identity(suite)
    inputs = _input_identity(
        suite,
        transformation,
        transformation_role=transformation_role,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        **identity,
        "inputs": inputs,
        "observation": observation.to_dict(),
    }
    validate_artifact("suite-execution", payload)
    write_json(path, payload)
    if evidence is not None:
        write_execution_evidence(
            path,
            evidence,
            suite_identity=identity,
            inputs=inputs,
            failure_stage=observation.failure_stage,
            error_summary=observation.error_summary,
        )
    return path


def read_observation(
    observations_root: Path,
    suite: GeneratedSuite,
    transformation: Path,
    *,
    transformation_role: TransformationRole = REFERENCE_TRANSFORMATION_ROLE,
) -> SuiteExecutionObservation | None:
    """The recorded observation for exactly these inputs, or ``None``.

    A record made from a different suite or a different transformation is not a
    result about this execution, so it is ignored rather than reused: that is
    what turns a stale artifact into a silent gate.
    """
    path = observation_path(observations_root, suite)
    if not path.is_file():
        return None
    payload = read_json(path)
    validate_artifact("suite-execution", payload)
    expected_identity = _suite_identity(suite)
    if any(payload.get(name) != value for name, value in expected_identity.items()):
        return None
    if payload.get("inputs") != _input_identity(
        suite,
        transformation,
        transformation_role=transformation_role,
    ):
        return None
    recorded = dict(payload.get("observation", {}))
    names = SuiteExecutionObservation.field_names()
    if not all(name in recorded for name in names):
        return None
    observation = SuiteExecutionObservation(**{name: recorded[name] for name in names})
    if recorded.get("technically_executable") != observation.is_technically_executable:
        return None
    if recorded.get("reference_valid") != observation.is_reference_valid:
        return None
    return observation


def _input_identity(
    suite: GeneratedSuite,
    transformation: Path,
    *,
    transformation_role: TransformationRole,
) -> dict[str, dict[str, str]]:
    return {
        "suite": ArtifactRef(
            path=repository_relative(suite.path),
            sha256=directory_sha256(suite.path),
            role="generated_suite",
        ).to_dict(),
        "transformation": ArtifactRef(
            path=repository_relative(transformation),
            sha256=file_sha256(transformation),
            role=transformation_role,
        ).to_dict(),
    }


def _suite_identity(suite: GeneratedSuite) -> dict[str, str]:
    return {
        "language": suite.language,
        "task": suite.task,
        "llm": suite.llm,
        "strategy": suite.strategy,
        "suite_id": suite.suite_id,
    }
