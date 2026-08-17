"""Application-level ordering, state, resume, and summary orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from llm4mtl import run_store
from llm4mtl.experiment_runner.adapters.test_generation import TestGenerationAdapter
from llm4mtl.experiment_runner.adapters.transformation_parser import (
    TransformationParserAdapter,
)
from llm4mtl.experiment_runner.adapters.transformation_validation import (
    TransformationValidationAdapter,
)
from llm4mtl.experiment_runner.config import (
    PIPELINE_STAGES,
    ConfigError,
    validate_config,
)
from llm4mtl.experiment_runner.models import PipelineConfig, RunResult, StageResult
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.provenance import build_provenance
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.semantic_tests.diagnosis_preparation import (
    prepare_after_execution_stage,
    prepare_execution_diagnosis,
)
from llm4mtl.semantic_tests.failure_report import (
    load_report_request,
    write_failure_report,
)
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.stage_contract import (
    CONTRACT_STAGE_IDS,
    contract_stage_id,
    stage_status,
    to_stage_payload,
)
from llm4mtl.workspace import materialize_engine


StageCallable = Callable[[PipelineConfig, bool], StageResult]
WORKSPACE_STAGES = {
    "technical_validation",
    "reference_validation",
    "transformation_validation",
}
_CONFIG_HASH_IGNORED_FIELDS = frozenset(
    {
        "resume",
        "force",
        "dry_run",
        "verbose",
        "output_format",
        "engine_dir",
        "run_dir",
    }
)


def _stages_require_workspace(stages: list[tuple[str, StageCallable]]) -> bool:
    return any(name in WORKSPACE_STAGES for name, _ in stages)


class ExperimentOrchestrator:
    """Coordinate deterministic local stages and run-store persistence."""

    def __init__(self, repo_root: Path | None = None) -> None:
        # Adapter subprocesses use this path as their cwd. After the v5 migration
        # every active component lives below the repository root.
        self.repo_root = (repo_root or REPO_ROOT).resolve()
        # v5 migration (Stage 4): runs are now run-centric under artifacts/work/runs.
        self.runs_root = TARGET.runs
        self.tests = TestGenerationAdapter(self.repo_root)
        self.parser = TransformationParserAdapter(self.repo_root)
        self.transformations = TransformationValidationAdapter(self.repo_root)

    def assemble_failure_report(
        self,
        request_path: Path,
        output_path: Path,
    ) -> dict[str, Any]:
        """Create one diagnosis evidence report from an existing run attempt.

        This is a deterministic post-execution command, not a contract stage:
        it neither invokes the diagnosis LLM nor modifies the run's manifest,
        events, or recorded stage attempts.
        """
        request = load_report_request(request_path)
        return write_failure_report(request, output_path)

    def prepare_diagnosis_evidence(
        self,
        run: str,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """Re-derive the diagnosis evidence of one recorded execution attempt.

        The same assembly the execution stage performs on its own. Exposed as a
        command so an existing run can be prepared without re-executing Maven,
        and so the automatic path has no behaviour that cannot be reproduced.
        """
        paths = run_store.open_run(self.runs_root, Path(run).name)
        if not paths.manifest.exists():
            raise ConfigError(f"unknown run: {run}")
        if attempt is None:
            attempts = existing_attempts(paths.stage_attempts_dir("execution"))
            if not attempts:
                raise ConfigError(
                    f"run {paths.root.name} recorded no execution attempt"
                )
            attempt = max(attempts)
        return prepare_execution_diagnosis(paths.root, attempt)

    def run(self, config: PipelineConfig) -> RunResult:
        validate_config(config)
        run_id = config.run_id or generate_run_id(config)
        config.run_id = run_id
        stages = self.stage_sequence(config)
        config_hash = stable_hash(
            config.to_dict(),
            ignored=_CONFIG_HASH_IGNORED_FIELDS,
        )
        # Resolve through the run store first: it validates that ``run_id`` is a
        # contained identifier. Deriving the directory here would let a
        # traversing id create files before anything checked it.
        paths = run_store.open_run(self.runs_root, run_id)
        run_dir = paths.root
        config.run_dir = str(run_dir)
        previous = self.load_previous(paths) if config.resume else {}
        identity = run_identity(config, config_hash)
        run_exists = paths.manifest.exists()

        run_conflicts_with_request = (
            run_dir.exists()
            and not config.dry_run
            and not config.resume
            and not config.force
        )
        if run_conflicts_with_request:
            raise ConfigError(f"Run already exists: {run_id}. Use --resume or --force.")

        if config.dry_run:
            results = [
                self.plan_stage(name, callback, config, config_hash)
                for name, callback in stages
            ]
            return RunResult(run_id, "dry_run", config.command, results)

        self._initialize_run(paths, identity, run_id, run_exists)

        if _stages_require_workspace(stages):
            # Execution always uses a run-local engine copy. `keep_workspace`
            # controls retention policy only; it must never decide whether runs
            # are isolated from the shared harness.
            config.engine_dir = str(self.prepare_workspace(run_dir, config.language))
        if not run_exists:
            write_json(run_dir / "config.resolved.yaml", config.to_dict())

        results = self._run_stages(
            stages,
            config,
            config_hash,
            previous,
            paths,
        )

        status = run_status(results)
        run_result = RunResult(
            run_id,
            status,
            config.command,
            results,
            str(run_dir.relative_to(REPO_ROOT)),
        )
        write_json(run_dir / "summary.json", run_result.to_dict())
        self.write_log(run_dir, run_result)
        run_store.append_event(paths, "run_finished", run_status=status)
        return run_result

    def _initialize_run(
        self,
        paths: run_store.RunPaths,
        identity: dict[str, object],
        run_id: str,
        run_exists: bool,
    ) -> None:
        if run_exists:
            # Identity is checked before any write or workspace materialization.
            # A rejected resume must leave every byte of the existing run intact.
            reject_identity_drift(
                run_store.read_manifest(paths) or {},
                identity,
                run_id,
            )
            run_store.append_event(paths, "run_resumed")
            return
        # Claim the immutable identity before creating any secondary run
        # artifact. Concurrent creators cannot materialize workspaces under an
        # identity they did not win.
        run_store.create_run(self.runs_root, run_id, identity)

    def _run_stages(
        self,
        stages: list[tuple[str, StageCallable]],
        config: PipelineConfig,
        config_hash: str,
        previous: dict[str, dict[str, object]],
        paths: run_store.RunPaths,
    ) -> list[StageResult]:
        results: list[StageResult] = []
        for name, callback in stages:
            result, should_stop = self._run_stage(
                name,
                callback,
                config,
                config_hash,
                previous.get(name),
                paths,
            )
            results.append(result)
            if should_stop:
                break
        return results

    def _run_stage(
        self,
        name: str,
        callback: StageCallable,
        config: PipelineConfig,
        config_hash: str,
        previous: dict[str, object] | None,
        paths: run_store.RunPaths,
    ) -> tuple[StageResult, bool]:
        plan = self.plan_stage(name, callback, config, config_hash)
        resumed = self.resume_stage(previous, plan, config)
        if resumed:
            self.apply_stage_outputs(name, resumed, config)
            stage_id = contract_stage_id(name)
            run_store.append_event(
                paths,
                "stage_skipped_resume",
                stage=stage_id,
                status=stage_status(stage_id, resumed),
            )
            return resumed, False
        if plan.status == "error":
            plan.config_hash = config_hash
            self._record_stage(paths, plan)
            return plan, config.fail_fast

        try:
            result = callback(config, False)
        except Exception as exc:
            result = StageResult(
                name,
                "infrastructure_error",
                {"infrastructure_errors": 1},
                {"error": f"{type(exc).__name__}: {exc}"},
                input_hash=plan.input_hash,
                exit_code=1,
            )
        result.config_hash = config_hash
        if not result.input_hash:
            result.input_hash = plan.input_hash
        self.apply_stage_outputs(name, result, config)
        self._record_stage(paths, result)
        should_stop = config.fail_fast and (
            result.status in {"error", "infrastructure_error"}
            or bool(result.domain_failures)
        )
        return result, should_stop

    def _record_stage(self, paths: run_store.RunPaths, result: StageResult) -> None:
        """Record one immutable stage attempt in the run-centric store.

        The persisted result is the same contract payload the stage service
        writes; the runner's internal detail is kept beside it as evidence.
        """
        stage = contract_stage_id(result.name)
        payload = to_stage_payload(stage, result)
        run_store.append_event(paths, "stage_started", stage=stage)
        attempt = run_store.record_attempt(
            paths,
            stage,
            payload,
            evidence=result.to_dict(),
        )
        run_store.append_event(
            paths,
            "stage_finished",
            stage=stage,
            status=payload["status"],
            outcome_code=payload["outcome_code"],
            attempt=attempt,
        )
        # Only now: the report assembler pins itself to the immutable attempt
        # that was just written, so it cannot run before that evidence exists.
        prepare_after_execution_stage(paths.root, stage, payload, attempt)

    def apply_stage_outputs(
        self,
        name: str,
        result: StageResult,
        config: PipelineConfig,
    ) -> None:
        if config.command != "pipeline.run" or name != "transformation_parsing":
            return
        passed = result.details.get("passed_transformations")
        if isinstance(passed, list):
            config.transformations = [str(path) for path in passed]
            config.transformation_selection_locked = True

    def stage_sequence(self, config: PipelineConfig) -> list[tuple[str, StageCallable]]:
        standalone = self._standalone_stage_sequence(config)
        if standalone is not None:
            return standalone

        stage_map: dict[str, tuple[str, StageCallable]] = {
            "extract": ("extraction", self.tests.extract),
            "technical": ("technical_validation", self.tests.technical_validation),
            "reference": ("reference_validation", self.tests.reference_validation),
            "parsing": ("transformation_parsing", self.parser.parse),
            "semantic": (
                "transformation_validation",
                self.transformations.semantic_validation,
            ),
        }
        enabled = {
            "technical": config.technical_validation,
            "reference": config.reference_validation,
            "parsing": config.transformation_parsing,
            "semantic": config.semantic_validation,
        }
        start = PIPELINE_STAGES.index(config.start_stage)
        stop = PIPELINE_STAGES.index(config.stop_after)
        return [
            stage_map[stage]
            for stage in PIPELINE_STAGES[start : stop + 1]
            if enabled.get(stage, True)
        ]

    def _standalone_stage_sequence(
        self, config: PipelineConfig
    ) -> list[tuple[str, StageCallable]] | None:
        if config.command == "tests.extract":
            return [("extraction", self.tests.extract)]
        if config.command == "tests.validate":
            if config.test_validation_stage == "technical":
                return [("technical_validation", self.tests.technical_validation)]
            if config.test_validation_stage == "reference":
                return [("reference_validation", self.tests.reference_validation)]
            return [
                ("technical_validation", self.tests.technical_validation),
                ("reference_validation", self.tests.reference_validation),
            ]
        if config.command == "transformations.parse":
            return [("transformation_parsing", self.parser.parse)]
        if config.command == "transformations.validate":
            return [
                (
                    "transformation_validation",
                    self.transformations.semantic_validation,
                )
            ]
        return None

    def plan_stage(
        self,
        name: str,
        callback: StageCallable,
        config: PipelineConfig,
        config_hash: str,
    ) -> StageResult:
        try:
            result = callback(config, True)
        except Exception as exc:
            result = StageResult(
                name,
                "error",
                {"infrastructure_errors": 1},
                {"error": f"{type(exc).__name__}: {exc}"},
                exit_code=1,
            )
        result.name = name
        result.config_hash = config_hash
        return result

    def resume_stage(
        self,
        previous_payload: dict[str, object] | None,
        plan: StageResult,
        config: PipelineConfig,
    ) -> StageResult | None:
        if not config.resume or config.force or not previous_payload:
            return None
        previous = StageResult.from_dict(previous_payload)
        if (
            previous.status in {"completed", "resumed", "skipped"}
            and previous.input_hash == plan.input_hash
            and previous.config_hash == plan.config_hash
        ):
            previous.status = "resumed"
            previous.details = {
                **previous.details,
                "resume_reason": "matching config and input hashes",
            }
            return previous
        return None

    def load_previous(self, paths: run_store.RunPaths) -> dict[str, dict[str, object]]:
        """Prior stage results, read from the run store's own evidence.

        Resume reads the same records everything else does. A separate progress
        file would be a second source of truth for what already ran, and the two
        could disagree about whether a stage may be skipped.
        """
        previous: dict[str, dict[str, object]] = {}
        for internal_name, stage in CONTRACT_STAGE_IDS.items():
            attempts = paths.stage_attempts_dir(stage)
            if not attempts.is_dir():
                continue
            for attempt in sorted(existing_attempts(attempts), reverse=True):
                evidence = paths.stage_attempt_evidence(stage, attempt)
                if evidence.is_file():
                    previous[internal_name] = read_json(evidence)
                    break
        return previous

    def prepare_workspace(self, run_dir: Path, language: str) -> Path:
        """Atomically materialize a run-local copy of the language's engine."""
        from llm4mtl.conventions import default_test_project_dir, language_config

        config = language_config(language)
        source = default_test_project_dir(config)
        return materialize_engine(
            source,
            run_dir / "workspaces",
            config.language_key,
        )

    def write_log(self, run_dir: Path, result: RunResult) -> None:
        """Write the human-readable runner log for a completed local run."""
        lines = self._log_lines(result)
        (run_dir / "runner.log").write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _log_lines(result: RunResult) -> list[str]:
        lines = [
            f"run_id={result.run_id}",
            f"status={result.status}",
            f"command={result.command}",
        ]
        for stage in result.stages:
            serialized_counts = json.dumps(stage.counts, sort_keys=True)
            lines.append(
                f"{stage.name}: status={stage.status} counts={serialized_counts}"
            )
            stdout = stage.details.get("stdout")
            stderr = stage.details.get("stderr")
            if stdout:
                lines.append(str(stdout).rstrip())
            if stderr:
                lines.append(str(stderr).rstrip())
        return lines


def run_identity(config: PipelineConfig, config_hash: str) -> dict[str, object]:
    """The immutable manifest fields for a locally started run.

    A run is exactly one combination, so each identity axis must resolve to one
    value. Leaving an axis open used to mean "select every value at stage time",
    which produced results a run id could not account for.
    """
    language = config.language.lower()
    task = exactly_one("task", config.tasks, required=True)
    return {
        "language": language,
        "task": task,
        # An axis no stage in this run consumes is recorded as null: not
        # applicable, which is different from unconstrained. A stage that needs a
        # null axis refuses rather than selecting every value.
        "transformation_model": exactly_one(
            "transformation model", config.transformation_models, required=False
        ),
        "test_generation_model": exactly_one(
            "test-generation model", config.test_models, required=False
        ),
        "transformation_strategy": exactly_one(
            "transformation strategy", config.transformation_strategies, required=False
        ),
        "test_generation_strategy": exactly_one(
            "test-generation strategy", config.test_strategies, required=False
        ),
        "seed": config.seed,
        "pipeline_variant": config.pipeline_variant,
        "provenance": build_provenance(
            language,
            task,
            command=config.command,
            config_hash=config_hash,
        ),
    }


def exactly_one(axis: str, values: list[str], *, required: bool) -> str | None:
    """The single value this run fixes for one identity axis.

    Several values are always a refusal: a run is one combination, and recording
    a set would make every result it produced unattributable.
    """
    if len(values) == 1:
        return values[0]
    if not values:
        if required:
            raise ConfigError(f"a run must fix its {axis}: none was selected")
        return None
    raise ConfigError(
        f"a run must fix its {axis}: {values!r} were selected. Use an experiment "
        "matrix to expand several values into one run each."
    )


IDENTITY_AXES = (
    "language",
    "task",
    "transformation_model",
    "test_generation_model",
    "transformation_strategy",
    "test_generation_strategy",
    "seed",
    "pipeline_variant",
)


def reject_identity_drift(
    manifest: dict[str, object],
    identity: dict[str, object],
    run_id: str,
) -> None:
    """Refuse to continue a run under a different identity than it was created with."""
    drifted = {
        axis: (manifest.get(axis), identity.get(axis))
        for axis in IDENTITY_AXES
        if manifest.get(axis) != identity.get(axis)
    }
    if drifted:
        described = "; ".join(
            f"{axis}: run is {was!r} but this invocation asks for {now!r}"
            for axis, (was, now) in sorted(drifted.items())
        )
        raise ConfigError(
            f"run {run_id} was created with a different identity ({described}). "
            "Start a new run instead of re-labelling an existing one."
        )


def generate_run_id(config: PipelineConfig) -> str:
    task = config.tasks[0].lower() if len(config.tasks) == 1 else "all"
    # Microseconds prevent two requests for the same task in one second from
    # sharing a run directory. Explicit IDs are still protected by the store.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{config.language}-{task}-{timestamp}"


def stable_hash(
    payload: dict[str, object],
    ignored: Collection[str] | None = None,
) -> str:
    excluded_fields = ignored or set()
    normalized = {
        key: value
        for key, value in payload.items()
        if key not in excluded_fields
    }
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_status(results: list[StageResult]) -> str:
    statuses = [
        stage_status(contract_stage_id(result.name), result)
        for result in results
    ]
    if any(status == "infrastructure_error" for status in statuses):
        return "failed"
    if any(status == "failed" for status in statuses):
        return "completed_with_failures"
    if any(status == "skipped" for status in statuses):
        return "incomplete"
    return "completed"
