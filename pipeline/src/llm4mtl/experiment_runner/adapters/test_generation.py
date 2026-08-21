"""Adapter for generated-test extraction and validation tools."""

from __future__ import annotations

import argparse
from pathlib import Path

from llm4mtl.conventions import (
    default_generated_tests_root,
    default_responses_root,
    language_config,
)
from llm4mtl.experiment_runner.adapters.base import fixed_selection, hash_paths
from llm4mtl.experiment_runner.config import ConfigError
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.languages import language_adapter
from llm4mtl.semantic_tests.extraction.cli import extract_one
from llm4mtl.semantic_tests.extraction.discovery import response_target_from_path
from llm4mtl.semantic_tests.reference_validation.runner import validate_suite
from llm4mtl.semantic_tests.suites.discovery import (
    candidate_suite_directories,
    suite_from_path,
)
from llm4mtl.semantic_tests.technical_validation.suite import check_suite
from llm4mtl.semantic_tests.validation import (
    ValidationContext,
    SuiteVerdict,
    reference_counts,
    technical_counts,
    workspace_for,
)

# Maven timeout for one suite execution. Matches the CLI default; the stage
# service has no per-request timeout of its own.
DEFAULT_SUITE_TIMEOUT_SECONDS = 240


class TestGenerationAdapter:
    """Stage entry points for generated-test extraction and validation.

    Nothing here names a language: every path is resolved from the run's own
    language, so adding one means adding its conventions and adapter, not
    editing this class.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()

    @staticmethod
    def responses_root(config: PipelineConfig) -> Path:
        return default_responses_root(language_config(config.language))

    @staticmethod
    def generated_tests_root(config: PipelineConfig) -> Path:
        return default_generated_tests_root(language_config(config.language))

    def extract(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        responses = self.select_responses(config)
        input_hash = hash_paths(responses)
        details = {"responses": [str(path) for path in responses]}
        if not responses:
            return StageResult(
                "extraction",
                "error",
                {"selected": 0, "failed": 1},
                details,
                input_hash,
            )
        if config.suite_id and len(responses) != 1:
            raise ConfigError(
                "--suite-id can only be used when exactly one response is selected."
            )
        if dry_run:
            return StageResult(
                "extraction",
                "dry_run",
                {"selected": len(responses)},
                details,
                input_hash,
            )

        extraction_args = argparse.Namespace(
            generated_tests_root=self.generated_tests_root(config),
            suite_id=config.suite_id,
            overwrite=config.overwrite,
            dry_run=False,
        )
        adapter = language_adapter(config.language)
        selected_model = fixed_selection(
            "test-generation model", config.test_models
        )[0]
        selected_strategy = fixed_selection("strategy", config.test_strategies)[0]
        selected_task = fixed_selection("task", config.tasks)[0]
        extraction_outcomes = []
        for response in responses:
            target = response_target_from_path(
                response_path=response,
                responses_root=self.responses_root(config),
                # Stage-service generation responses are run-scoped rather than
                # filed below the shared <model>/<strategy> convenience tree.
                # Their identity comes from the immutable manifest, while the
                # filename must still agree with its one task.
                llm_override=selected_model,
                strategy_override=selected_strategy,
                task_override=selected_task,
            )
            extracted, message = extract_one(target, extraction_args, adapter)
            extraction_outcomes.append(
                {
                    "response": str(response),
                    "extracted": extracted,
                    "detail": message,
                }
            )

        created = sum(
            1 for outcome in extraction_outcomes if outcome["extracted"]
        )
        details["outcomes"] = extraction_outcomes
        return StageResult(
            "extraction",
            "completed",
            {
                "selected": len(responses),
                "created": created,
                "failed": len(responses) - created,
            },
            details,
            input_hash,
        )

    def technical_validation(
        self,
        config: PipelineConfig,
        dry_run: bool,
    ) -> StageResult:
        return self._validate_suites(
            name="technical_validation",
            config=config,
            dry_run=dry_run,
            judge_as_oracle=False,
        )

    def reference_validation(
        self,
        config: PipelineConfig,
        dry_run: bool,
    ) -> StageResult:
        return self._validate_suites(
            name="reference_validation",
            config=config,
            dry_run=dry_run,
            judge_as_oracle=True,
        )

    def _validate_suites(
        self,
        name: str,
        config: PipelineConfig,
        dry_run: bool,
        judge_as_oracle: bool,
    ) -> StageResult:
        """Run a validation gate in-process and count its typed verdicts.

        The verdicts come from the same functions the CLI uses, so the stage's
        counts are the gate's own decisions rather than a second interpretation
        of its printed output.
        """
        suite_paths = self.select_candidate_suites(config)
        input_hash = hash_paths(suite_paths)
        details: dict[str, object] = {"suites": [str(path) for path in suite_paths]}
        if not suite_paths:
            return StageResult(
                name,
                "error",
                {"selected": 0, "failed": 1},
                details,
                input_hash,
            )
        if dry_run:
            return StageResult(
                name,
                "dry_run",
                {"selected": len(suite_paths)},
                details,
                input_hash,
            )

        context = self.validation_context(config)
        verdicts = self._suite_verdicts(
            suite_paths,
            config,
            context,
            judge_as_oracle,
        )

        counts = (
            reference_counts(verdicts, len(suite_paths))
            if judge_as_oracle
            else technical_counts(verdicts, len(suite_paths))
        )
        details["verdicts"] = [
            {
                "suite": str(verdict.suite.path),
                "status": verdict.status,
            }
            for verdict in verdicts
        ]
        if counts.get("skipped"):
            details["skip_reason"] = (
                "SKIPPED_NOT_EXECUTABLE"
                if judge_as_oracle
                else "SKIPPED_ARTIFACT_INVALID"
            )
        return StageResult(name, "completed", counts, details, input_hash)

    def _suite_verdicts(
        self,
        suite_paths: list[Path],
        config: PipelineConfig,
        context: ValidationContext,
        judge_as_oracle: bool,
    ) -> list[SuiteVerdict]:
        """Run the selected validation gate over immutable suite candidates."""
        validate = validate_suite if judge_as_oracle else check_suite
        generated_tests_root = self.generated_tests_root(config)
        return [
            validate(
                suite_from_path(path, generated_tests_root, config.language),
                context,
            )
            for path in suite_paths
        ]

    def validation_context(self, config: PipelineConfig) -> ValidationContext:
        if not config.engine_dir:
            raise ConfigError(
                "suite validation requires a run-local engine workspace"
            )
        engine_dir = Path(config.engine_dir)
        return ValidationContext(
            adapter=language_adapter(config.language),
            workspace=workspace_for(engine_dir, self.observations_root(config)),
            timeout=DEFAULT_SUITE_TIMEOUT_SECONDS,
        )

    def observations_root(self, config: PipelineConfig) -> Path:
        """Where this run records suite-execution observations.

        Scoping them to the run is what lets reference validation reuse the
        technical stage's execution without a result from an earlier run
        deciding anything about this one. The orchestrator resolves this path
        through the run store before invoking an adapter.
        """
        if not config.run_dir:
            raise ConfigError(
                "a resolved run directory is required: suite-execution observations "
                "must belong to the current run"
            )
        return Path(config.run_dir).resolve() / "observations"

    def select_responses(self, config: PipelineConfig) -> list[Path]:
        if config.responses:
            return sorted(
                Path(path).resolve()
                for path in config.responses
                if Path(path).is_file()
            )
        tasks = set(config.tasks)
        models = fixed_selection("test-generation model", config.test_models)
        strategies = fixed_selection("strategy", config.test_strategies)
        return sorted(
            path.resolve()
            for path in self.responses_root(config).glob("*/*/*.md")
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
        models = fixed_selection("test-generation model", config.test_models)
        strategies = fixed_selection("strategy", config.test_strategies)
        suites = sorted(
            path
            for path in candidate_suite_directories(self.generated_tests_root(config))
            if path.parts[-3] in models
            and path.parts[-2] in strategies
            and (config.all_tasks or path.parts[-5] in tasks)
            and (not config.suite_id or path.name == config.suite_id)
        )
        return suites
