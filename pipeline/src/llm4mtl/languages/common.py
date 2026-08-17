"""Shared mechanics used by concrete language adapters.

This module contains no language decisions. It only provides the repeatable
parts of adapter implementation: static candidate checks, run-local parser
materialization, temporary harness injection, Maven evidence classification,
and normalization of common execution failures.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Mapping

from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    OutcomeStatus,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.external_tools.maven import run_maven
from llm4mtl.languages.base import Workspace
from llm4mtl.semantic_tests.suite_execution import (
    classify_maven_run,
    execution_workspace_lock,
    snapshot_dir,
)
from llm4mtl.semantic_tests.execution_evidence import (
    RawExecutionEvidence,
    capture_execution_evidence,
)
from llm4mtl.semantic_tests.suites.java import infer_fqcn
from llm4mtl.semantic_tests.suites.metadata import artifact_invalid_reason
from llm4mtl.semantic_tests.surefire import UNCLASSIFIED_RUNTIME, read_surefire_reports
from llm4mtl.semantic_tests.technical_validation.resources import check_models_load
from llm4mtl.semantic_tests.technical_validation.smoke import junit_test_method_counts
from llm4mtl.workspace.injection import Injection
from llm4mtl.workspace.materialization import materialize_engine


def validate_rendered_suite(
    suite: GeneratedSuite,
    *,
    contract_exists: bool,
) -> ArtifactValidation:
    """Perform language-neutral checks without executing generated code."""
    reason = artifact_invalid_reason(suite.path)
    java_paths = sorted(suite.path.glob("*.java"))
    model_paths = sorted(
        path for path in (suite.path / "models").rglob("*") if path.is_file()
    )
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
            reason_code="ARTIFACT_INVALID",
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
    """Return the first static rendered-suite violation in contract order."""
    if not contract_exists:
        return (
            "No deterministic task contract exists for "
            f"{suite.language}/{suite.task}"
        )
    if not java_paths:
        return "No deterministic Java harness found in suite root"
    if not model_paths:
        return "No generated model/resource files found under models/"
    if not any(junit_test_method_counts(java_paths).values()):
        return "No JUnit @Test methods found in the rendered harness"
    models_load, model_error = check_models_load(model_paths)
    return "" if models_load else model_error


def materialize_parser(
    source: Path,
    workspace: Workspace,
    language: str,
) -> Path:
    """Copy a frozen parser beneath the current run before Maven may touch it."""
    return materialize_engine(
        source,
        workspace.engine_dir.parent,
        f"{language}-parser",
    )


def execute_maven_suite(
    suite: GeneratedSuite,
    transformation: Path,
    workspace: Workspace,
    timeout: int,
    *,
    transformation_destination: Path,
    java_root: Path,
    models_root: Path,
    maven_cwd: Path,
    maven_command: list[str],
    reports_root: Path,
) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
    """Inject one suite into its run-local harness and classify one Maven run.

    Returns the observation and the raw evidence behind it, read while the
    workspace lock is still held: the next execution's ``mvn clean`` deletes the
    reports this one produced.
    """
    java_paths = sorted(suite.path.glob("*.java"))
    model_paths = sorted(
        path for path in (suite.path / "models").rglob("*") if path.is_file()
    )

    with execution_workspace_lock(workspace.engine_dir):
        injection = Injection()
        try:
            injection.copy_file(transformation, transformation_destination)
            for java_path in java_paths:
                fqcn = infer_fqcn(java_path)
                injection.copy_file(
                    java_path,
                    java_root / Path(*fqcn.split(".")).with_suffix(".java"),
                )
            for model_path in model_paths:
                injection.copy_file(
                    model_path,
                    models_root / model_path.relative_to(suite.path / "models"),
                )

            selectors = ",".join(infer_fqcn(path) for path in java_paths)
            command = [
                part.replace("{selectors}", selectors)
                for part in maven_command
            ]
            command.append(
                "-Dllm4mtl.observations.dir="
                f"{snapshot_dir(workspace.observations_dir, suite)}"
            )
            result = run_maven(command, cwd=maven_cwd, timeout=timeout)
            reports = read_surefire_reports(reports_root)
            evidence = capture_execution_evidence(result, reports_root, reports)
        finally:
            injection.restore()
    return classify_maven_run(result, reports), evidence


def normalize_failure(
    observation: SuiteExecutionObservation,
) -> TransformationOutcome | None:
    """Map shared execution phases without fabricating successful snapshots.

    Reached only from the generated-transformation stage, whose pairs are all
    reference-validated: the suite compiled, ran, and its assertions held
    against the trusted reference. A throw here is therefore a failure of this
    pairing, and ``unclassified_runtime`` maps to the same runtime outcome as a
    recognized engine throw. Which sub-phase threw is unknown, but the phase is
    not — and whether the transformation or the test should be refined is Source
    Diagnosis's decision, made later from the recorded evidence.
    """
    if observation.timed_out:
        return TransformationOutcome(
            status=OutcomeStatus.TIMED_OUT,
            diagnostic=observation.error_summary,
        )
    status = {
        "transformation_parse": OutcomeStatus.PARSE_FAILED,
        "java_compilation": OutcomeStatus.COMPILE_FAILED,
        "engine_runtime": OutcomeStatus.RUNTIME_FAILED,
        UNCLASSIFIED_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
        "infrastructure": OutcomeStatus.INFRASTRUCTURE_FAILED,
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
    namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
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
