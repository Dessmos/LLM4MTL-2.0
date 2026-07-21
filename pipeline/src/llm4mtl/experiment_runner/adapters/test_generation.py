"""Adapter for generated-test extraction and validation tools."""

from __future__ import annotations

import re
from pathlib import Path

from llm4mtl.experiment_runner.adapters.base import hash_paths, python_command, run_command
from llm4mtl.experiment_runner.config import ALLOWED_MODELS, ALLOWED_STRATEGIES, ConfigError
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult


class TestGenerationAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.test_generation_root = self.repo_root / "Test_Generation"
        self.responses_root = (
            self.test_generation_root
            / "Workflows"
            / "n8n-docker"
            / "mtl_snippets"
            / "ETL_test_generation"
            / "responses"
        )
        self.generated_tests_root = self.test_generation_root / "generated_tests" / "etl"
        self.results_root = self.test_generation_root / "results" / "etl"
        # v5 migration: the test-generation driver scripts moved into the pipeline
        # package; the data dirs above still live in the nested Test_Generation folder.
        from llm4mtl.paths import TARGET

        semantic_tests = TARGET.package / "semantic_tests"
        self.extract_script = semantic_tests / "extraction" / "extract_generated_suite.py"
        self.technical_script = (
            semantic_tests / "technical_validation" / "check_generated_suite_technical_validity.py"
        )
        self.reference_script = (
            semantic_tests / "reference_validation" / "validate_generated_suite_against_reference.py"
        )

    def extract(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        responses = self.select_responses(config)
        input_hash = hash_paths(responses)
        details = {"responses": [str(path) for path in responses]}
        if not responses:
            return StageResult("extraction", "error", {"selected": 0, "failed": 1}, details, input_hash)
        if config.suite_id and len(responses) != 1:
            raise ConfigError("--suite-id can only be used when exactly one response is selected.")
        if dry_run:
            return StageResult("extraction", "dry_run", {"selected": len(responses)}, details, input_hash)

        command = python_command(self.extract_script)
        for response in responses:
            command.extend(("--response", str(response)))
        if config.suite_id:
            command.extend(("--suite-id", config.suite_id))
        if config.overwrite:
            command.append("--overwrite")
        execution = run_command(command, self.repo_root, config.verbose)
        match = re.search(r"Extracted:\s*(\d+);\s*failed:\s*(\d+)", execution.stdout)
        created = int(match.group(1)) if match else 0
        failed = int(match.group(2)) if match else (1 if execution.exit_code else 0)
        details.update(command=command, stdout=execution.stdout, stderr=execution.stderr)
        return StageResult(
            "extraction",
            "completed" if match else "infrastructure_error",
            {"selected": len(responses), "created": created, "failed": failed},
            details,
            input_hash,
            exit_code=execution.exit_code,
        )

    def technical_validation(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        suites = self.select_candidate_suites(config)
        return self._validate_suites(
            name="technical_validation",
            script=self.technical_script,
            suites=suites,
            config=config,
            dry_run=dry_run,
            marker="technically_valid",
            passed_key="passed",
        )

    def reference_validation(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        suites = self.select_candidate_suites(config)
        return self._validate_suites(
            name="reference_validation",
            script=self.reference_script,
            suites=suites,
            config=config,
            dry_run=dry_run,
            marker="valid",
            passed_key="validated",
        )

    def _validate_suites(
        self,
        name: str,
        script: Path,
        suites: list[Path],
        config: PipelineConfig,
        dry_run: bool,
        marker: str,
        passed_key: str,
    ) -> StageResult:
        input_hash = hash_paths(suites)
        details = {"suites": [str(path) for path in suites]}
        if not suites:
            return StageResult(name, "error", {"selected": 0, "failed": 1}, details, input_hash)
        if dry_run:
            return StageResult(name, "dry_run", {"selected": len(suites)}, details, input_hash)

        command = python_command(script)
        for suite in suites:
            command.extend(("--suite", str(suite)))
        if config.etl_test_dir:
            command.extend(("--etl-test-dir", config.etl_test_dir))
        execution = run_command(command, self.repo_root, config.verbose)
        values = re.findall(rf"\b{re.escape(marker)}=(True|False)\b", execution.stdout)
        reference_statuses = (
            re.findall(r"\bstatus=(VALIDATED|REFERENCE_INVALID|INFRASTRUCTURE_ERROR)\b", execution.stdout)
            if name == "reference_validation"
            else []
        )
        passed = (
            sum(value == "VALIDATED" for value in reference_statuses)
            if reference_statuses
            else sum(value == "True" for value in values)
        )
        failed = (
            sum(value == "REFERENCE_INVALID" for value in reference_statuses)
            if reference_statuses
            else sum(value == "False" for value in values)
        )
        infrastructure_errors = sum(
            value == "INFRASTRUCTURE_ERROR" for value in reference_statuses
        )
        executed_count = len(reference_statuses) if reference_statuses else len(values)
        skipped = max(0, len(suites) - executed_count)
        details.update(command=command, stdout=execution.stdout, stderr=execution.stderr)
        counts = {
            "selected": len(suites),
            passed_key: passed,
            "failed" if name == "technical_validation" else "invalid": failed,
            "skipped": skipped,
        }
        if name == "reference_validation":
            counts["infrastructure_errors"] = infrastructure_errors
        missing_technical = (
            name == "reference_validation"
            and "No technically valid candidate suites" in execution.stderr
        )
        status = (
            "completed"
            if values or execution.exit_code == 0 or missing_technical
            else "infrastructure_error"
        )
        if name == "reference_validation" and skipped:
            details["skip_reason"] = "SKIPPED_MISSING_TECHNICAL_VALIDATION"
        return StageResult(name, status, counts, details, input_hash, exit_code=execution.exit_code)

    def select_responses(self, config: PipelineConfig) -> list[Path]:
        if config.responses:
            return sorted(Path(path).resolve() for path in config.responses if Path(path).is_file())
        tasks = set(config.tasks)
        models = set(config.test_models) or ALLOWED_MODELS
        strategies = set(config.test_strategies) or ALLOWED_STRATEGIES
        return sorted(
            path.resolve()
            for path in self.responses_root.glob("*/*/*.md")
            if path.parent.parent.name in models
            and path.parent.name in strategies
            and (config.all_tasks or path.stem in tasks)
        )

    def select_candidate_suites(self, config: PipelineConfig) -> list[Path]:
        if config.suites:
            return sorted(
                Path(path).resolve()
                for path in config.suites
                if Path(path).is_dir() and "candidates" in Path(path).parts
            )
        tasks = set(config.tasks)
        models = set(config.test_models) or ALLOWED_MODELS
        strategies = set(config.test_strategies) or ALLOWED_STRATEGIES
        suites = sorted(
            path.resolve()
            for path in self.generated_tests_root.glob("*/candidates/*/*/suite_*")
            if path.is_dir()
            and path.parts[-3] in models
            and path.parts[-2] in strategies
            and (config.all_tasks or path.parts[-5] in tasks)
            and (not config.suite_id or path.name == config.suite_id)
        )
        return suites
