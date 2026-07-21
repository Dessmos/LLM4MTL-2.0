"""Technical validation flow for one extracted candidate suite."""

from __future__ import annotations

import argparse

from llm4mtl.workspace.injection import Injection
from llm4mtl.external_tools.maven import run_maven, summarize_error
from llm4mtl.semantic_tests.suites.injection import inject_suite
from llm4mtl.semantic_tests.suites.java import infer_fqcn
from llm4mtl.semantic_tests.suites.metadata import contract_invalid_reason
from llm4mtl.semantic_tests.suites.models import CandidateSuite
from llm4mtl.semantic_tests.technical_validation.models import LANGUAGE
from llm4mtl.semantic_tests.technical_validation.resources import check_models_load
from llm4mtl.semantic_tests.technical_validation.smoke import junit_test_method_counts, surefire_test_selector


def check_suite(suite: CandidateSuite, args: argparse.Namespace) -> dict[str, str]:
    java_paths = sorted(suite.path.glob("*.java"))
    model_paths = sorted((suite.path / "models").rglob("*")) if (suite.path / "models").exists() else []
    model_paths = [path for path in model_paths if path.is_file()]

    java_present = bool(java_paths)
    models_present = bool(model_paths)
    models_load, model_error = check_models_load(model_paths)

    result = {
        "language": LANGUAGE,
        "task": suite.task,
        "suite_id": suite.suite_id,
        "llm": suite.llm,
        "strategy": suite.strategy,
        "java_present": str(java_present),
        "models_present": str(models_present),
        "contract_valid": "True",
        "compiles": "False",
        "models_load": str(models_load),
        "junit_executes": "False",
        "technically_valid": "False",
        "maven_exit_code": "",
        "error_summary": "",
    }

    # Fail-fast: a suite that violated its task contract at extraction time must
    # not proceed to Maven; surface the recorded reason here instead.
    contract_reason = contract_invalid_reason(suite.path)
    if contract_reason:
        result["contract_valid"] = "False"
        result["error_summary"] = contract_reason
        return result

    if not java_present:
        result["error_summary"] = "No Java file found in suite root"
        return result
    if not models_present:
        result["error_summary"] = "No generated model/resource files found under models/"
        return result
    test_counts = junit_test_method_counts(java_paths)
    if not any(count > 0 for count in test_counts.values()):
        result["error_summary"] = "No JUnit @Test methods found in generated Java files"
        return result
    if not models_load:
        result["error_summary"] = model_error
        return result

    injection = Injection()
    try:
        inject_suite(suite, java_paths, model_paths, args.etl_test_dir.resolve(), injection)
        class_names = [infer_fqcn(path) for path in java_paths]
        test_selector = surefire_test_selector(class_names)

        compile_result = run_maven(
            ["mvn", "clean", "test-compile", "-DskipTests"],
            cwd=args.etl_test_dir.resolve(),
            timeout=args.timeout,
        )
        result["maven_exit_code"] = str(compile_result.exit_code)
        if compile_result.exit_code != 0:
            result["error_summary"] = summarize_error(compile_result.output)
            return result
        result["compiles"] = "True"

        smoke_result = run_maven(
            ["mvn", "test", f"-Dtest={test_selector}"],
            cwd=args.etl_test_dir.resolve(),
            timeout=args.timeout,
        )
        result["maven_exit_code"] = str(smoke_result.exit_code)
        if smoke_result.exit_code != 0:
            result["error_summary"] = summarize_error(smoke_result.output)
            return result

        result["junit_executes"] = "True"
        result["technically_valid"] = "True"
        return result
    finally:
        injection.restore()
