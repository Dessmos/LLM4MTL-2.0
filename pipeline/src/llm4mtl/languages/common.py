"""Shared mechanics used by concrete language adapters.

This module makes no language-specific decisions. It holds the parts adapters
share: static suite checks, copying the parser into the run, running parser
commands, injecting a suite into the harness, running and classifying Maven,
and mapping common execution failures.
"""

from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    OutcomeStatus,
    ParseObservation,
    RawExecutionEvidence,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.domain.observations import ARTIFACT_INVALID_REASON, FailureStage
from llm4mtl.external_tools.maven import (
    POM_NAMESPACE,
    TEST_SELECTION_OPTION_PREFIX,
    run_maven,
)
from llm4mtl.languages.base import Workspace
from llm4mtl.semantic_tests.semantic_spec import MODELS_DIRECTORY
from llm4mtl.semantic_tests.suite_execution import (
    OBSERVATIONS_DIR_OPTION,
    classify_maven_run,
    execution_workspace_lock,
    snapshot_dir,
)
from llm4mtl.semantic_tests.execution_evidence import capture_execution_evidence
from llm4mtl.semantic_tests.suites.java import JAVA_SOURCE_GLOB, infer_fqcn
from llm4mtl.semantic_tests.suites.metadata import artifact_invalid_reason
from llm4mtl.semantic_tests.surefire import read_surefire_reports
from llm4mtl.semantic_tests.technical_validation.resources import check_models_load
from llm4mtl.semantic_tests.technical_validation.smoke import junit_test_method_counts
from llm4mtl.workspace.injection import Injection
from llm4mtl.workspace.materialization import materialize_engine

# How long one parser command may run before it is stopped.
PARSER_TIMEOUT_SECONDS = 900
# The most characters of tool output kept as one parse diagnostic.
DIAGNOSTIC_MAX_CHARS = 500
# The placeholder in a Maven command that becomes the test class selectors.
SELECTORS_PLACEHOLDER = "{selectors}"
# The Maven option that runs only the suite's own test classes.
TEST_SELECTION_OPTION = f"{TEST_SELECTION_OPTION_PREFIX}{SELECTORS_PLACEHOLDER}"
# In a multi-module build, lets modules with none of the selected tests pass.
ALLOW_MODULES_WITHOUT_SELECTED_TESTS = "-Dsurefire.failIfNoSpecifiedTests=false"


def validate_rendered_suite(
    suite: GeneratedSuite,
    *,
    contract_exists: bool,
) -> ArtifactValidation:
    """Perform language-neutral checks without executing generated code."""
    reason = artifact_invalid_reason(suite.path)
    java_paths = _suite_java_paths(suite)
    model_paths = _suite_model_paths(suite)
    if not reason:
        reason = _rendered_suite_invalid_reason(
            suite,
            contract_exists=contract_exists,
            java_paths=java_paths,
            model_paths=model_paths,
        )

    if reason:
        return ArtifactValidation(
            valid=False,
            reason_code=ARTIFACT_INVALID_REASON,
            violations=(reason,),
        )
    return ArtifactValidation(valid=True, contract_applied=True)


def _rendered_suite_invalid_reason(
    suite: GeneratedSuite,
    *,
    contract_exists: bool,
    java_paths: list[Path],
    model_paths: list[Path],
) -> str:
    """The first static problem of a rendered suite, or ``""`` when there is none."""
    if not contract_exists:
        return (
            "No deterministic task contract exists for "
            f"{suite.language}/{suite.task}"
        )
    if not java_paths:
        return "No deterministic Java harness found in suite root"
    if not model_paths:
        return (
            "No generated model/resource files found under "
            f"{MODELS_DIRECTORY}/"
        )
    if not any(junit_test_method_counts(java_paths).values()):
        return "No JUnit @Test methods found in the rendered harness"
    models_load, model_error = check_models_load(model_paths)
    return "" if models_load else model_error


def _suite_java_paths(suite: GeneratedSuite) -> list[Path]:
    return sorted(suite.path.glob(JAVA_SOURCE_GLOB))


def _suite_model_paths(suite: GeneratedSuite) -> list[Path]:
    models_dir = suite.path / MODELS_DIRECTORY
    return sorted(path for path in models_dir.rglob("*") if path.is_file())


def materialize_parser(
    source: Path,
    workspace: Workspace,
    language: str,
) -> Path:
    """Copy the frozen parser into the run, so Maven never writes into the original."""
    return materialize_engine(
        source,
        workspace.engine_dir.parent,
        f"{language}-parser",
    )


def run_parser_command(
    command: Sequence[str],
    parser_dir: Path,
    timeout_seconds: int = PARSER_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run one parser or parser-build command and capture its text output.

    Raises ``subprocess.TimeoutExpired`` when the command runs too long.
    """
    return subprocess.run(
        command,
        cwd=parser_dir,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def combined_output(completed: subprocess.CompletedProcess[str]) -> str:
    """Standard output, then standard error, of a finished command."""
    return f"{completed.stdout}\n{completed.stderr}"


def diagnostic_tail(output: str) -> str:
    """The end of ``output``, where build tools print the cause of a failure."""
    return output.strip()[-DIAGNOSTIC_MAX_CHARS:]


def failed_for_every_file(
    transformations: Sequence[Path],
    diagnostic: str,
) -> dict[Path, ParseObservation]:
    """The same failed parse for every file, when the parser itself failed."""
    return {
        path: ParseObservation(parsed=False, diagnostic=diagnostic)
        for path in transformations
    }


@dataclass(frozen=True)
class MavenHarness:
    """Where one language's harness takes a suite, and how Maven runs it.

    ``maven_command`` may contain ``{selectors}``; it is replaced by the
    comma-separated test classes of the suite.
    """

    transformation_destination: Path
    java_root: Path
    models_root: Path
    maven_cwd: Path
    maven_command: tuple[str, ...]
    reports_root: Path


def execute_maven_suite(
    suite: GeneratedSuite,
    transformation: Path,
    workspace: Workspace,
    timeout: int,
    harness: MavenHarness,
) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
    """Inject one suite into its run-local harness and classify one Maven run.

    Returns the observation and the raw evidence behind it, read while the
    workspace lock is still held: the next execution's ``mvn clean`` deletes the
    reports this one produced.
    """
    with execution_workspace_lock(workspace.engine_dir):
        injection = Injection()
        try:
            _inject_suite(injection, suite, transformation, harness)
            command = _maven_command(harness, suite, workspace)
            result = run_maven(command, cwd=harness.maven_cwd, timeout=timeout)
            reports = read_surefire_reports(harness.reports_root)
            evidence = capture_execution_evidence(
                result, harness.reports_root, reports
            )
        finally:
            injection.restore()
    return classify_maven_run(result, reports), evidence


def _inject_suite(
    injection: Injection,
    suite: GeneratedSuite,
    transformation: Path,
    harness: MavenHarness,
) -> None:
    """Copy the transformation, the Java classes, and the models into the harness."""
    injection.copy_file(transformation, harness.transformation_destination)
    for java_path in _suite_java_paths(suite):
        fqcn = infer_fqcn(java_path)
        injection.copy_file(
            java_path,
            harness.java_root / Path(*fqcn.split(".")).with_suffix(".java"),
        )
    models_dir = suite.path / MODELS_DIRECTORY
    for model_path in _suite_model_paths(suite):
        injection.copy_file(
            model_path,
            harness.models_root / model_path.relative_to(models_dir),
        )


def _maven_command(
    harness: MavenHarness,
    suite: GeneratedSuite,
    workspace: Workspace,
) -> list[str]:
    """The harness command for this suite's classes and observation folder."""
    selectors = ",".join(infer_fqcn(path) for path in _suite_java_paths(suite))
    command = [
        part.replace(SELECTORS_PLACEHOLDER, selectors)
        for part in harness.maven_command
    ]
    command.append(
        f"{OBSERVATIONS_DIR_OPTION}{snapshot_dir(workspace.observations_dir, suite)}"
    )
    return command


def normalize_failure(
    observation: SuiteExecutionObservation,
) -> TransformationOutcome | None:
    """Map a failed execution phase to a transformation outcome.

    Only the generated-transformation stage calls this. Its suites already
    passed against the reference transformation, so a throw here is a runtime
    failure of this transformation/suite pair, even when the exact sub-phase
    (``unclassified_runtime``) is unknown. Whether the transformation or the
    test needs fixing is decided later by Source Diagnosis.

    Returns ``None`` for phases this table does not map, such as a run that
    reached its assertions.
    """
    if observation.timed_out:
        return TransformationOutcome(
            status=OutcomeStatus.TIMED_OUT,
            diagnostic=observation.error_summary,
        )
    status = {
        FailureStage.TRANSFORMATION_PARSE: OutcomeStatus.PARSE_FAILED,
        FailureStage.JAVA_COMPILATION: OutcomeStatus.COMPILE_FAILED,
        # The suite's own models loaded on the reference, so a load failure here
        # is the generated transformation naming a model or metamodel wrongly.
        FailureStage.MODEL_LOADING: OutcomeStatus.RUNTIME_FAILED,
        FailureStage.ENGINE_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
        FailureStage.UNCLASSIFIED_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
        FailureStage.INFRASTRUCTURE: OutcomeStatus.INFRASTRUCTURE_FAILED,
    }.get(observation.failure_stage)
    if status is None:
        return None
    return TransformationOutcome(status=status, diagnostic=observation.error_summary)


def pom_properties(
    pom: Path,
    requested: Mapping[str, str],
) -> dict[str, str]:
    """Read required Maven property versions for immutable provenance."""
    try:
        root = ET.parse(pom).getroot()
    except (OSError, ET.ParseError) as exc:
        raise RuntimeError(f"cannot read Maven versions from {pom}") from exc
    namespace = {"m": POM_NAMESPACE}
    properties = root.find("m:properties", namespace)
    if properties is None:
        raise RuntimeError(f"Maven project has no properties: {pom}")
    versions: dict[str, str] = {}
    for label, property_name in requested.items():
        value = properties.findtext(f"m:{property_name}", namespaces=namespace)
        if not value:
            raise RuntimeError(f"{pom} omits Maven property {property_name}")
        versions[label] = value
    return versions
