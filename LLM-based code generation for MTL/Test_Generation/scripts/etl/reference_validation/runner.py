"""Reference validation flow for one generated candidate suite."""

from __future__ import annotations

from pathlib import Path

from common.injection import Injection
from common.maven import run_maven, summarize_error
from etl.reference_validation.maven_status import compiles, executes
from etl.reference_validation.models import ReferenceValidationContext, ReferenceValidationResult
from etl.reference_validation.promotion import promote_validated_suite
from etl.reference_validation.reference import inject_reference_transformation
from etl.technical_validation.java import infer_fqcn
from etl.technical_validation.models import CandidateSuite
from etl.technical_validation.suite import inject_suite


def validate_suite(
    suite: CandidateSuite,
    context: ReferenceValidationContext,
) -> ReferenceValidationResult:
    java_paths = sorted(suite.path.glob("*.java"))
    model_paths = suite_model_paths(suite.path)

    if not java_paths:
        return failed_before_maven(suite, "No Java file found in suite root")
    if not model_paths:
        return failed_before_maven(suite, "No generated model/resource files found under models/")

    injection = Injection()
    try:
        reference_ok, reference_error = inject_reference_transformation(
            suite.task,
            context.etl_test_dir,
            context.references_root,
            injection,
        )
        if not reference_ok:
            return failed_before_maven(suite, reference_error)

        inject_suite(suite, java_paths, model_paths, context.etl_test_dir, injection)
        test_selector = ",".join(infer_fqcn(path) for path in java_paths)
        maven_result = run_maven(
            ["mvn", "clean", "test", f"-Dtest={test_selector}"],
            cwd=context.etl_test_dir,
            timeout=context.timeout,
        )

        did_compile = compiles(maven_result)
        did_execute = did_compile and executes(maven_result)
        passed = maven_result.exit_code == 0
        result = ReferenceValidationResult(
            suite=suite,
            compiles=did_compile,
            executes=did_execute,
            reference_pass=passed,
            valid=passed,
            maven_exit_code=maven_result.exit_code,
            error_summary="" if passed else summarize_error(maven_result.output),
        )
        if result.valid and context.promote:
            promote_validated_suite(suite, result.as_row())
        return result
    finally:
        injection.restore()


def suite_model_paths(suite_path: Path) -> list[Path]:
    models_dir = suite_path / "models"
    if not models_dir.exists():
        return []
    return sorted(path for path in models_dir.rglob("*") if path.is_file())


def failed_before_maven(suite: CandidateSuite, error: str) -> ReferenceValidationResult:
    return ReferenceValidationResult(
        suite=suite,
        compiles=False,
        executes=False,
        reference_pass=False,
        valid=False,
        maven_exit_code="",
        error_summary=error,
    )
