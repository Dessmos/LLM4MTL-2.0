"""The stages that extract generated suites and validate them technically and
against the reference transformation."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.conventions import (
    default_generated_tests_root,
    default_responses_root,
    language_config,
)
from llm4mtl.languages import language_adapter
from llm4mtl.run_store.models import RunPaths
from llm4mtl.semantic_tests.extraction.discovery import response_target_from_path
from llm4mtl.semantic_tests.extraction.extract import extract_one
from llm4mtl.semantic_tests.extraction.models import ExtractionOptions
from llm4mtl.semantic_tests.reference_validation.runner import validate_suite
from llm4mtl.semantic_tests.suites.discovery import suite_from_path
from llm4mtl.semantic_tests.technical_validation.suite import check_suite
from llm4mtl.semantic_tests.validation import (
    ValidationContext,
    SuiteVerdict,
    reference_counts,
    technical_counts,
    workspace_for,
)
from llm4mtl.stages.models import (
    EXTRACTION_STAGE_NAME,
    REFERENCE_VALIDATION_STAGE_NAME,
    SUITE_TIMEOUT_SECONDS,
    TECHNICAL_VALIDATION_STAGE_NAME,
    ConfigError,
    PipelineConfig,
    StageResult,
)
from llm4mtl.stages.selection import (
    dry_run_result,
    existing_files,
    fixed_selection,
    hash_paths,
    nothing_selected_result,
    select_candidate_suites,
    select_generated_files,
)

RESPONSE_EXTENSION = "md"


class TestGenerationAdapter:
    """Stage entry points for generated-test extraction and validation.

    Nothing here names a language: every path is resolved from the run's own
    language, so adding one means adding its conventions and adapter, not
    editing this class.
    """

    @staticmethod
    def responses_root(config: PipelineConfig) -> Path:
        return default_responses_root(language_config(config.language))

    @staticmethod
    def generated_tests_root(config: PipelineConfig) -> Path:
        return default_generated_tests_root(language_config(config.language))

    def extract(self, config: PipelineConfig, dry_run: bool) -> StageResult:
        responses = self.select_responses(config)
        input_hash = hash_paths(responses)
        details: dict[str, object] = {"responses": [str(path) for path in responses]}
        if not responses:
            return nothing_selected_result(EXTRACTION_STAGE_NAME, details, input_hash)
        if config.suite_id and len(responses) != 1:
            raise ConfigError(
                "--suite-id can only be used when exactly one response is selected."
            )
        if dry_run:
            return dry_run_result(
                EXTRACTION_STAGE_NAME, len(responses), details, input_hash
            )

        outcomes = self._extract_responses(config, responses)
        created = sum(1 for outcome in outcomes if outcome["extracted"])
        details["outcomes"] = outcomes
        return StageResult(
            EXTRACTION_STAGE_NAME,
            "completed",
            {
                "selected": len(responses),
                "created": created,
                "failed": len(responses) - created,
            },
            details,
            input_hash,
        )

    def _extract_responses(
        self,
        config: PipelineConfig,
        responses: list[Path],
    ) -> list[dict[str, object]]:
        """Extract one candidate suite per response and report each outcome."""
        options = ExtractionOptions(
            generated_tests_root=self.generated_tests_root(config),
            suite_id=config.suite_id,
        )
        adapter = language_adapter(config.language)
        identity = _response_identity(config)
        responses_root = self.responses_root(config)
        outcomes: list[dict[str, object]] = []
        for response in responses:
            target = response_target_from_path(
                response_path=response,
                responses_root=responses_root,
                **identity,
            )
            extracted, message = extract_one(target, options, adapter)
            outcomes.append(
                {"response": str(response), "extracted": extracted, "detail": message}
            )
        return outcomes

    def technical_validation(
        self,
        config: PipelineConfig,
        dry_run: bool,
    ) -> StageResult:
        return self._validate_suites(
            name=TECHNICAL_VALIDATION_STAGE_NAME,
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
            name=REFERENCE_VALIDATION_STAGE_NAME,
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
            return nothing_selected_result(name, details, input_hash)
        if dry_run:
            return dry_run_result(name, len(suite_paths), details, input_hash)

        context = self.validation_context(config)
        verdicts = self._suite_verdicts(
            suite_paths,
            config,
            context,
            judge_as_oracle,
        )
        count = reference_counts if judge_as_oracle else technical_counts
        counts = count(verdicts, len(suite_paths))
        details["verdicts"] = [_verdict_detail(verdict) for verdict in verdicts]
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
        return [
            validate(
                suite_from_path(path, config.language),
                context,
            )
            for path in suite_paths
        ]

    def validation_context(self, config: PipelineConfig) -> ValidationContext:
        if not config.engine_dir:
            raise ConfigError("suite validation requires a run-local engine workspace")
        engine_dir = Path(config.engine_dir)
        return ValidationContext(
            adapter=language_adapter(config.language),
            workspace=workspace_for(engine_dir, self.observations_root(config)),
            timeout=SUITE_TIMEOUT_SECONDS,
        )

    def observations_root(self, config: PipelineConfig) -> Path:
        """Where this run records suite-execution observations.

        Scoping them to the run lets reference validation reuse the technical
        stage's execution, while no result from an earlier run decides anything
        about this one. Both entry points set ``config.run_dir`` through the run
        store before they call a stage.
        """
        if not config.run_dir:
            raise ConfigError(
                "a resolved run directory is required: suite-execution observations "
                "must belong to the current run"
            )
        return RunPaths(Path(config.run_dir).resolve()).observations_dir

    def select_responses(self, config: PipelineConfig) -> list[Path]:
        if config.responses:
            return existing_files(config.responses)
        models = fixed_selection("test-generation model", config.test_models)
        strategies = fixed_selection("strategy", config.test_strategies)
        return select_generated_files(
            self.responses_root(config),
            RESPONSE_EXTENSION,
            config,
            models=models,
            strategies=strategies,
        )

    def select_candidate_suites(self, config: PipelineConfig) -> list[Path]:
        return select_candidate_suites(config, self.generated_tests_root(config))


def _single_identity_value(axis: str, values: list[str]) -> str:
    selected = fixed_selection(axis, values)
    if len(selected) != 1:
        raise ConfigError(
            f"extraction requires exactly one {axis}; selected {len(selected)}"
        )
    return next(iter(selected))


def _response_identity(config: PipelineConfig) -> dict[str, str]:
    """The identity every selected response is extracted under.

    Stage-service responses live in the run, not below the shared
    <model>/<strategy> tree, so their path does not name the model or strategy.
    The identity comes from the run's selections instead (the stage service
    fills them from the manifest); the filename must still match the one task.
    """
    return {
        "llm_override": _single_identity_value(
            "test-generation model", config.test_models
        ),
        "strategy_override": _single_identity_value(
            "strategy", config.test_strategies
        ),
        "task_override": _single_identity_value("task", config.tasks),
    }


def _verdict_detail(verdict: SuiteVerdict) -> dict[str, object]:
    return {
        "suite": str(verdict.suite.path),
        "status": verdict.status,
        "failure_stage": verdict.failure_stage,
        "error_summary": verdict.error_summary,
    }
