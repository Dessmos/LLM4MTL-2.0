"""Adapter for semantic evaluation of generated transformations."""

from __future__ import annotations

import re
from pathlib import Path

from llm4mtl.experiment_runner.adapters.base import hash_paths, python_command, run_command
from llm4mtl.experiment_runner.config import ALLOWED_MODELS, ALLOWED_STRATEGIES
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult


class TransformationValidationAdapter:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        from llm4mtl.paths import TARGET

        # v5 final cleanup: generated test suites live under artifacts/work/test_generation.
        self.validated_tests_root = TARGET.artifacts_work / "test_generation" / "generated_tests" / "etl"
        # v5 migration (Stage 3): the transformation-generation n8n tree moved to
        # workflows/n8n/transformations.
        from llm4mtl.paths import TARGET

        self.transformations_root = (
            TARGET.workflows
            / "transformations"
            / "mtl_snippets"
            / "ETL_language"
            / "responses"
        )
        # The validation driver is package-owned; selected data remains external.
        from llm4mtl.paths import TARGET

        self.script = (
            TARGET.package / "transformation_execution" / "validate_generated_transformations.py"
        )

    def semantic_validation(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        suites = self.select_validated_suites(config)
        transformations = self.select_transformations(config)
        pairs = [
            (suite, transformation)
            for suite in suites
            for transformation in transformations
            if suite.parts[-5] == transformation.stem
        ]
        input_hash = hash_paths(suites + transformations)
        details = {
            "validated_suites": [str(path) for path in suites],
            "transformations": [str(path) for path in transformations],
            "pairs": [f"{suite} × {transformation}" for suite, transformation in pairs],
        }
        counts = {
            "selected_suites": len(suites),
            "selected_transformations": len(transformations),
            "execution_pairs": len(pairs),
        }
        if not pairs:
            if config.transformation_selection_locked and not transformations:
                counts["skipped"] = 1
                details["skip_reason"] = "SKIPPED_NO_PARSED_TRANSFORMATIONS"
                return StageResult(
                    "transformation_validation",
                    "skipped",
                    counts,
                    details,
                    input_hash,
                )
            counts["failed"] = 1
            return StageResult("transformation_validation", "error", counts, details, input_hash)
        if dry_run:
            return StageResult("transformation_validation", "dry_run", counts, details, input_hash)

        command = python_command(self.script)
        for suite in suites:
            command.extend(("--suite", str(suite)))
        for transformation in transformations:
            command.extend(("--transformation", str(transformation)))
        if config.etl_test_dir:
            command.extend(("--etl-test-dir", config.etl_test_dir))
        execution = run_command(command, self.repo_root, config.verbose)
        statuses = re.findall(r"\bstatus=(passed|failed)\b", execution.stdout)
        artifacts: list[dict[str, str]] = []
        pending_status: str | None = None
        for line in execution.stdout.splitlines():
            status_match = re.search(r"\bstatus=(passed|failed)\b", line)
            if status_match:
                pending_status = status_match.group(1)
            if line.strip().startswith("artifacts:") and pending_status:
                artifacts.append(
                    {"status": pending_status, "path": line.split("artifacts:", 1)[1].strip()}
                )
                pending_status = None
        counts.update(
            evaluated=len(statuses),
            passed=sum(status == "passed" for status in statuses),
            failed=sum(status == "failed" for status in statuses),
        )
        details.update(
            command=command,
            stdout=execution.stdout,
            stderr=execution.stderr,
            artifacts=artifacts,
        )
        status = "completed" if statuses else "infrastructure_error"
        return StageResult(
            "transformation_validation",
            status,
            counts,
            details,
            input_hash,
            exit_code=execution.exit_code,
        )

    def select_validated_suites(self, config: PipelineConfig) -> list[Path]:
        if config.suites:
            return sorted(
                Path(path).resolve()
                for path in config.suites
                if Path(path).is_dir() and "validated" in Path(path).parts
            )
        tasks = set(config.tasks)
        models = set(config.test_models) or ALLOWED_MODELS
        strategies = set(config.test_strategies) or ALLOWED_STRATEGIES
        return sorted(
            path.resolve()
            for path in self.validated_tests_root.glob("*/validated/*/*/suite_*")
            if path.is_dir()
            and path.parts[-3] in models
            and path.parts[-2] in strategies
            and (config.all_tasks or path.parts[-5] in tasks)
            and (not config.suite_id or path.name == config.suite_id)
        )

    def select_transformations(self, config: PipelineConfig) -> list[Path]:
        if config.transformations or config.transformation_selection_locked:
            return sorted(Path(path).resolve() for path in config.transformations if Path(path).is_file())
        tasks = set(config.tasks)
        models = set(config.transformation_models) or ALLOWED_MODELS
        strategies = set(config.transformation_strategies) or ALLOWED_STRATEGIES
        return sorted(
            path.resolve()
            for path in self.transformations_root.glob("*/*/*.etl")
            if path.parent.parent.name in models
            and path.parent.name in strategies
            and (config.all_tasks or path.stem in tasks)
        )
