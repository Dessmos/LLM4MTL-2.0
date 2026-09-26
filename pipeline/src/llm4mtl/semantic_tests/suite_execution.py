"""One execution of a generated suite, recorded as several separate facts.

Running a suite answers two different questions, and they must not be mixed:

* *technical executability* — did the rendered harness compile, were the tests
  found, did the models load, did the transformation engine run at all?
* *oracle validity* — run against the trusted reference transformation, do the
  generated assertions hold?

A suite whose assertions fail answered the first question with yes and the
second with no. Counting it as a technical failure would drop wrong oracles from
the reference-pass population and lower the executability rate, which breaks
every rate derived from the funnel.

So both answers come from ONE Maven run against the reference transformation.
The observation is recorded, and a later stage reads it instead of running Maven
again. The same code records runs of reference-valid suites against generated
transformations.
"""

from __future__ import annotations

import fcntl
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.domain import (
    ArtifactRef,
    GeneratedSuite,
    RawExecutionEvidence,
    SuiteExecutionObservation,
)
from llm4mtl.domain.observations import FailureStage
from llm4mtl.external_tools.maven import (
    TEST_SELECTION_OPTION_PREFIX,
    CommandResult,
    run_maven,
    summarize_error,
)
from llm4mtl.paths import repository_relative
from llm4mtl.semantic_tests.reference_validation.maven_status import (
    compiles,
    executes,
    transformation_parse_failed,
)
from llm4mtl.semantic_tests.reference_validation.reference import (
    transformation_destination,
)
from llm4mtl.semantic_tests.execution_evidence import (
    capture_execution_evidence,
    write_execution_evidence,
)
from llm4mtl.semantic_tests.suites.injection import inject_suite
from llm4mtl.semantic_tests.suites.java import JAVA_SOURCE_GLOB, infer_fqcn
from llm4mtl.semantic_tests.semantic_spec import MODELS_DIRECTORY
from llm4mtl.semantic_tests.surefire import (
    SUREFIRE_REPORTS_DIR,
    SurefireReport,
    read_surefire_reports,
)
from llm4mtl.serialization.hashing import directory_sha256, file_sha256
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.workspace.injection import Injection

SCHEMA_VERSION = "2.0"
OBSERVATION_SCHEMA = "suite-execution"
OBSERVATION_FILENAME = "suite_execution.json"
# The harness system property that names the folder for actual output models.
OBSERVATIONS_DIR_OPTION = "-Dllm4mtl.observations.dir="
# The folder beside an observation that holds the actual output models.
SNAPSHOTS_DIRNAME = "snapshots"
GENERATED_SUITE_ROLE = "generated_suite"
REFERENCE_TRANSFORMATION_ROLE = "reference_transformation"
GENERATED_TRANSFORMATION_ROLE = "generated_transformation"
TransformationRole = Literal[
    "reference_transformation",
    "generated_transformation",
]

# The harness threw before it could judge the assertions.
_STAGES_BEFORE_THE_ORACLE = frozenset(
    {
        FailureStage.MODEL_LOADING,
        FailureStage.TRANSFORMATION_PARSE,
        FailureStage.ENGINE_RUNTIME,
        FailureStage.UNCLASSIFIED_RUNTIME,
    }
)
# Of those, the stages that are only reached after the models loaded.
_STAGES_WITH_MODELS_LOADED = frozenset(
    {FailureStage.TRANSFORMATION_PARSE, FailureStage.ENGINE_RUNTIME}
)


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
    """Derive the separate observations from one Maven run.

    Maven's console output cannot tell the harness phases apart: a model that
    did not load, an engine that threw, and a failed assertion all print as
    ``Tests run: N, Failures: F, Errors: E``. Treating them alike would count a
    broken test as executable and its breakage as a disagreement with the
    reference. The Surefire reports do tell them apart, so they decide whenever
    they exist. A timeout or a compile failure is read from the command result
    first; the console is only a fallback for a compiled run with no readable
    report.
    """
    did_compile = compiles(result)
    if result.timed_out:
        return _phase_failure(result, FailureStage.TIMEOUT, compiled=did_compile)
    if not did_compile:
        return _phase_failure(result, FailureStage.JAVA_COMPILATION, compiled=False)

    # Only the total absence of readable XML may fall back to the console. A
    # report that parsed and counted zero tests is evidence that nothing ran,
    # and `_classify_from_reports` turns it into a test-discovery failure.
    if reports is None:
        return _classify_from_console(result)
    return _classify_from_reports(result, reports)


def _classify_from_reports(
    result: CommandResult, reports: SurefireReport
) -> SuiteExecutionObservation:
    if reports.tests == 0:
        return _phase_failure(result, FailureStage.TEST_DISCOVERY, compiled=True)

    failure_stage = reports.failure_stage()
    if failure_stage in _STAGES_BEFORE_THE_ORACLE:
        return _harness_failure(result, reports, failure_stage)

    assertions_passed = reports.failures == 0 and reports.errors == 0
    return _assertions_evaluated(
        result,
        assertions_passed=assertions_passed,
        error_summary=(
            ""
            if assertions_passed
            else reports.first_failure or summarize_error(result.output)
        ),
    )


def _harness_failure(
    result: CommandResult, reports: SurefireReport, failure_stage: str
) -> SuiteExecutionObservation:
    """The harness never got far enough to judge the oracle."""
    return SuiteExecutionObservation(
        compiled=True,
        tests_discovered=True,
        models_loaded=failure_stage in _STAGES_WITH_MODELS_LOADED,
        engine_started=failure_stage == FailureStage.ENGINE_RUNTIME,
        assertions_evaluated=False,
        assertions_passed=False,
        timed_out=False,
        maven_exit_code=result.exit_code,
        failure_stage=failure_stage,
        error_summary=(
            reports.first_error
            or reports.first_failure
            or summarize_error(result.output)
        ),
    )


def _classify_from_console(result: CommandResult) -> SuiteExecutionObservation:
    """Fallback when no Surefire report exists: only coarse phases are knowable.

    Only a compiled run reaches this fallback.
    """
    if transformation_parse_failed(result.output):
        return _phase_failure(result, FailureStage.TRANSFORMATION_PARSE, compiled=True)

    counts = _console_test_counts(result.output)
    if not executes(result) or counts is None or counts.tests == 0:
        # No XML, and nothing in the console shows that a test ran. An exit
        # code of 0 in that state is not evidence of a passing suite: it is what
        # `-Dsurefire.failIfNoSpecifiedTests=false` produces when the selector
        # matched nothing, and treating it as success would validate a suite
        # that never executed.
        return _phase_failure(result, FailureStage.TEST_DISCOVERY, compiled=True)
    if _console_shows_unexplained_error(result, counts):
        return _phase_failure(
            result,
            FailureStage.UNCLASSIFIED_RUNTIME,
            compiled=True,
            tests_discovered=True,
        )

    assertions_passed = result.exit_code == 0 and counts.failures == 0
    return _assertions_evaluated(
        result,
        assertions_passed=assertions_passed,
        error_summary="" if assertions_passed else summarize_error(result.output),
    )


def _console_shows_unexplained_error(
    result: CommandResult, counts: _ConsoleTestCounts
) -> bool:
    """Whether a test threw, or Maven failed with no failed assertion.

    Console summaries distinguish JUnit errors from assertion failures but do
    not identify which harness phase threw. Without XML, naming a phase would
    invent evidence.
    """
    return counts.errors > 0 or (result.exit_code != 0 and counts.failures == 0)


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


def _assertions_evaluated(
    result: CommandResult, *, assertions_passed: bool, error_summary: str
) -> SuiteExecutionObservation:
    """The harness ran every phase and judged the assertions."""
    return SuiteExecutionObservation(
        compiled=True,
        tests_discovered=True,
        models_loaded=True,
        engine_started=True,
        assertions_evaluated=True,
        assertions_passed=assertions_passed,
        timed_out=False,
        maven_exit_code=result.exit_code,
        failure_stage="" if assertions_passed else FailureStage.ASSERTION_FAILURE,
        error_summary=error_summary,
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
        timed_out=failure_stage == FailureStage.TIMEOUT,
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

    The transformation is always copied in explicitly. Executability only means
    something for a known transformation, and the harness ships its own copies
    that would otherwise be used silently.

    ``observations_root`` is where the harness writes the actual target models.
    Passing ``None`` means this execution keeps no snapshot; that is the
    caller's choice.

    Returns the observation and the raw evidence behind it. The evidence is read
    while the workspace lock is still held, because the next execution's
    ``mvn clean`` deletes these reports.
    """
    java_paths, model_paths = _suite_artifact_paths(suite)

    # A run can receive concurrent stage requests. Each run has its own
    # workspace; this lock stops two executions of the same run from copying
    # files into it at the same time.
    with execution_workspace_lock(test_project_dir):
        injection = Injection()
        try:
            injection.copy_file(
                transformation,
                transformation_destination(test_project_dir, suite.task),
            )
            inject_suite(suite, java_paths, model_paths, test_project_dir, injection)
            return _run_and_observe(
                suite, java_paths, test_project_dir, timeout, observations_root
            )
        finally:
            injection.restore()


def _run_and_observe(
    suite: GeneratedSuite,
    java_paths: list[Path],
    test_project_dir: Path,
    timeout: int,
    observations_root: Path | None,
) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
    """Run Maven once in the injected workspace and read what it left behind."""
    command = _maven_command(java_paths, observations_root, suite)
    result = run_maven(command, cwd=test_project_dir, timeout=timeout)
    # `mvn clean` wipes target/ first, so these reports describe this run only.
    reports_root = test_project_dir / SUREFIRE_REPORTS_DIR
    reports = read_surefire_reports(reports_root)
    evidence = capture_execution_evidence(result, reports_root, reports)
    return classify_maven_run(result, reports), evidence


def _suite_artifact_paths(suite: GeneratedSuite) -> tuple[list[Path], list[Path]]:
    """Return deterministic Java and model input paths for ``suite``."""
    java_paths = sorted(suite.path.glob(JAVA_SOURCE_GLOB))
    model_paths = sorted(
        path for path in (suite.path / MODELS_DIRECTORY).rglob("*") if path.is_file()
    )
    return java_paths, model_paths


def _maven_command(
    java_paths: list[Path],
    observations_root: Path | None,
    suite: GeneratedSuite,
) -> list[str]:
    """Build the Maven command for one suite execution."""
    selector = ",".join(infer_fqcn(path) for path in java_paths)
    command = ["mvn", "clean", "test", f"{TEST_SELECTION_OPTION_PREFIX}{selector}"]
    if observations_root is not None:
        observations_dir = snapshot_dir(observations_root, suite)
        command.append(f"{OBSERVATIONS_DIR_OPTION}{observations_dir}")
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

    The folder sits beside the observation, not beside the transformation. A
    snapshot belongs to one transformation, suite, test case, and model slot;
    the harness creates the test-case folder below this one. A folder shared by
    all suites of one transformation would let two suites with the same case
    name overwrite each other's output, and a diagnosis would then cite the
    wrong output.
    """
    return observation_path(observations_root, suite).parent / SNAPSHOTS_DIRNAME


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

    Validated on write: the funnel's denominators come from these records, so a
    malformed one would silently corrupt a metric instead of failing a stage.

    When ``evidence`` is given, it is archived beside the observation in the
    same call, so the run keeps the full Maven output and Surefire reports
    behind this observation. This cannot wait until the end of the stage: the
    next execution's ``mvn clean`` wipes those reports.
    """
    path = observation_path(observations_root, suite)
    identity = _suite_identity(suite)
    inputs = _input_identity(
        suite, transformation, transformation_role=transformation_role
    )
    _write_observation(path, identity, inputs, observation)
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


def _write_observation(
    path: Path,
    identity: dict[str, str],
    inputs: dict[str, dict[str, str]],
    observation: SuiteExecutionObservation,
) -> None:
    """Validate the observation record against its schema, then write it."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        **identity,
        "inputs": inputs,
        "observation": observation.to_dict(),
    }
    validate_artifact(OBSERVATION_SCHEMA, payload)
    write_json(path, payload)


def read_observation(
    observations_root: Path,
    suite: GeneratedSuite,
    transformation: Path,
    *,
    transformation_role: TransformationRole = REFERENCE_TRANSFORMATION_ROLE,
) -> SuiteExecutionObservation | None:
    """The recorded observation for exactly these inputs, or ``None``.

    A record made from a different suite or transformation says nothing about
    this execution, so it is ignored. Reusing it would let a stale file decide
    the verdict without anyone noticing.
    """
    path = observation_path(observations_root, suite)
    if not path.is_file():
        return None
    payload = read_json(path)
    validate_artifact(OBSERVATION_SCHEMA, payload)
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
            role=GENERATED_SUITE_ROLE,
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
