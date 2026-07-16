"""Run one validated suite against one generated ETL transformation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from common.injection import Injection
from common.maven import run_maven, summarize_error
from etl.reference_validation.maven_status import compiles, executes
from etl.reference_validation.reference import transformation_destination
from etl.suites.injection import inject_suite, suite_model_paths
from etl.suites.java import infer_fqcn
from transformation_validation.hashing import directory_sha256, file_sha256
from transformation_validation.models import TransformationValidationResult, ValidationPair


def make_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ")


def validate_pair(pair: ValidationPair, etl_test_dir: Path, timeout: int) -> TransformationValidationResult:
    transformation_hash = file_sha256(pair.transformation.path)
    suite_hash = directory_sha256(pair.suite.path)
    run_id = make_run_id()

    input_error = validate_inputs(pair)
    if input_error:
        return TransformationValidationResult(
            pair=pair,
            run_id=run_id,
            transformation_sha256=transformation_hash,
            suite_sha256=suite_hash,
            status="failed",
            failure_stage="input_validation",
            compiles=False,
            executes=False,
            tests_pass=False,
            maven_exit_code="",
            timed_out=False,
            error_summary=input_error,
            maven_output="",
        )

    java_paths = sorted(pair.suite.path.glob("*.java"))
    model_paths = suite_model_paths(pair.suite.path)
    injection = Injection()
    try:
        try:
            injection.copy_file(
                pair.transformation.path,
                transformation_destination(etl_test_dir, pair.suite.task),
            )
            inject_suite(
                pair.suite.as_candidate(),
                java_paths,
                model_paths,
                etl_test_dir,
                injection,
            )
            test_selector = ",".join(infer_fqcn(path) for path in java_paths)
            maven_result = run_maven(
                ["mvn", "clean", "test", f"-Dtest={test_selector}"],
                cwd=etl_test_dir,
                timeout=timeout,
            )
        except (OSError, RuntimeError) as exc:
            return infrastructure_failure(
                pair,
                run_id,
                transformation_hash,
                suite_hash,
                exc,
            )
    finally:
        injection.restore()

    did_compile = compiles(maven_result)
    did_execute = did_compile and executes(maven_result)
    passed = maven_result.exit_code == 0 and did_execute
    return TransformationValidationResult(
        pair=pair,
        run_id=run_id,
        transformation_sha256=transformation_hash,
        suite_sha256=suite_hash,
        status="passed" if passed else "failed",
        failure_stage="" if passed else failure_stage(maven_result.output, did_compile, did_execute, maven_result.timed_out),
        compiles=did_compile,
        executes=did_execute,
        tests_pass=passed,
        maven_exit_code=maven_result.exit_code,
        timed_out=maven_result.timed_out,
        error_summary="" if passed else summarize_error(maven_result.output),
        maven_output=maven_result.output,
    )


def validate_inputs(pair: ValidationPair) -> str:
    if not pair.transformation.path.is_file():
        return f"Generated transformation not found: {pair.transformation.path}"
    if not pair.suite.path.is_dir():
        return f"Validated suite not found: {pair.suite.path}"
    if not list(pair.suite.path.glob("*.java")):
        return f"No Java file found in validated suite: {pair.suite.path}"
    if not suite_model_paths(pair.suite.path):
        return f"No generated model files found in validated suite: {pair.suite.path / 'models'}"
    return ""


def failure_stage(output: str, did_compile: bool, did_execute: bool, timed_out: bool) -> str:
    if timed_out:
        return "timeout"
    if not did_compile:
        return "java_compilation"
    if "ETL parse errors" in output or "ParseProblem" in output:
        return "transformation_parse"
    if not did_execute:
        return "test_discovery"
    return "test_failure"


def infrastructure_failure(
    pair: ValidationPair,
    run_id: str,
    transformation_hash: str,
    suite_hash: str,
    error: Exception,
) -> TransformationValidationResult:
    message = f"{type(error).__name__}: {error}"
    return TransformationValidationResult(
        pair=pair,
        run_id=run_id,
        transformation_sha256=transformation_hash,
        suite_sha256=suite_hash,
        status="failed",
        failure_stage="infrastructure",
        compiles=False,
        executes=False,
        tests_pass=False,
        maven_exit_code="",
        timed_out=False,
        error_summary=message[:500],
        maven_output=message,
    )
