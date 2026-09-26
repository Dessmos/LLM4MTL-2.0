"""Application-level ordering, state, resume, and summary orchestration."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection
from pathlib import Path
from typing import Any

from llm4mtl import run_store
from llm4mtl.experiment_runner.config import PIPELINE_STAGES, validate_config
from llm4mtl.experiment_runner.models import RunResult
from llm4mtl.paths import REPO_ROOT, TARGET, ArtifactRoots
from llm4mtl.provenance import build_provenance
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.identity import generate_run_id, validate_opaque_id
from llm4mtl.semantic_tests.diagnosis_aggregation import aggregate_run_diagnoses
from llm4mtl.semantic_tests.diagnosis_preparation import prepare_execution_diagnosis
from llm4mtl.semantic_tests.failure_report import (
    read_request_payload,
    write_report,
)
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.stage_contract import (
    CONTRACT_STAGE_IDS,
    contract_stage_id,
    stage_status,
)
from llm4mtl.stage_recording import (
    announce_stage_start,
    infrastructure_error_result,
    record_stage_attempt,
)
from llm4mtl.stages.dispatch import (
    WORKSPACE_STAGES,
    StageCallable,
    StageImplementations,
    prepare_workspace,
)
from llm4mtl.stages.models import (
    EXTRACTION_STAGE_NAME,
    REFERENCE_VALIDATION_STAGE_NAME,
    TECHNICAL_VALIDATION_STAGE_NAME,
    TRANSFORMATION_PARSING_STAGE_NAME,
    TRANSFORMATION_VALIDATION_STAGE_NAME,
    ConfigError,
    PipelineConfig,
    StageResult,
)
from llm4mtl.vocabulary import EXECUTION_STAGE_ID


_CONFIG_HASH_IGNORED_FIELDS = frozenset(
    {
        "resume",
        "force",
        "dry_run",
        "output_format",
        "engine_dir",
        "run_dir",
        # Where the run is filed, not what it computes.
        "batch_id",
    }
)

# ``--start-stage``/``--stop-after`` step -> the internal stage it runs.
_PIPELINE_STEP_STAGES = {
    "extract": EXTRACTION_STAGE_NAME,
    "technical": TECHNICAL_VALIDATION_STAGE_NAME,
    "reference": REFERENCE_VALIDATION_STAGE_NAME,
    "parsing": TRANSFORMATION_PARSING_STAGE_NAME,
    "semantic": TRANSFORMATION_VALIDATION_STAGE_NAME,
}
# Commands that run a fixed stage list instead of a pipeline interval.
_STANDALONE_COMMAND_STAGES = {
    "tests.extract": (EXTRACTION_STAGE_NAME,),
    "transformations.parse": (TRANSFORMATION_PARSING_STAGE_NAME,),
    "transformations.validate": (TRANSFORMATION_VALIDATION_STAGE_NAME,),
}
# ``tests validate --stage`` -> the stages it runs. Any other value runs both.
_TEST_VALIDATION_STAGES = {
    "technical": (TECHNICAL_VALIDATION_STAGE_NAME,),
    "reference": (REFERENCE_VALIDATION_STAGE_NAME,),
}
_ALL_TEST_VALIDATION_STAGES = (
    TECHNICAL_VALIDATION_STAGE_NAME,
    REFERENCE_VALIDATION_STAGE_NAME,
)
# Statuses that end the run early under ``--fail-fast``.
_FAILED_STAGE_STATUSES = frozenset({"error", "infrastructure_error"})
# Previously recorded statuses that ``--resume`` may reuse.
_RESUMABLE_STAGE_STATUSES = frozenset({"completed", "resumed", "skipped"})


def _stages_require_workspace(stages: list[tuple[str, StageCallable]]) -> bool:
    return any(contract_stage_id(name) in WORKSPACE_STAGES for name, _ in stages)


class ExperimentOrchestrator:
    """Coordinate deterministic local stages and run-store persistence."""

    def __init__(self) -> None:
        # The one statement of where runs, batches and diagnoses live. Tests
        # point it at a temporary tree.
        self.artifacts: ArtifactRoots = TARGET.artifact_roots
        stages = StageImplementations()
        self.tests = stages.tests
        self.parser = stages.parser
        self.transformations = stages.transformations

    def assemble_failure_report(
        self,
        request_path: Path,
        output_path: Path,
        scope: str = "test_case",
    ) -> dict[str, Any]:
        """Create one diagnosis evidence report from an existing run attempt.

        This is a deterministic post-execution command, not a contract stage:
        it neither invokes the diagnosis LLM nor modifies the run's manifest,
        events, or recorded stage attempts.
        """
        payload = read_request_payload(request_path)
        return write_report(payload, output_path, scope=scope)

    def prepare_diagnosis_evidence(
        self,
        batch_id: str,
        run_id: str,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """Re-derive the diagnosis evidence of one recorded execution attempt.

        The same assembly the execution stage performs on its own. Exposed as a
        command so an existing run can be prepared without re-executing Maven,
        and so the automatic path has no behaviour that cannot be reproduced.
        """
        paths = self._existing_run(batch_id, run_id)
        if attempt is None:
            attempt = _latest_execution_attempt(paths)
        return prepare_execution_diagnosis(paths.root, attempt)

    def aggregate_diagnosis_evidence(
        self,
        batch_id: str,
        run_id: str,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        """Cluster one attempt's prepared reports by the failure they describe.

        Read-only. The pipeline keeps one report and one verdict per failing
        test case; this counts how many distinct failures those observations
        actually cover, and how far the separate verdicts agreed.
        """
        paths = self._existing_run(batch_id, run_id)
        if attempt is None:
            attempt = _latest_execution_attempt(paths)
        return aggregate_run_diagnoses(
            paths.root, attempt, self.artifacts.run_diagnoses_dir(batch_id, run_id)
        )

    def _existing_run(self, batch_id: str, run_id: str) -> run_store.RunPaths:
        batch = run_store.open_batch(self.artifacts.runs, batch_id)
        if run_store.read_batch_manifest(batch) is None:
            raise ConfigError(f"unknown batch: {batch_id}")
        paths = run_store.open_run(batch.root, run_id)
        if not paths.manifest.exists():
            raise ConfigError(f"unknown run: {batch_id}/{run_id}")
        return paths

    def _batch_for(self, config: PipelineConfig) -> run_store.BatchPaths:
        """The batch this invocation files its run under.

        A named batch must already exist: a run resumed or added by id joins a
        launch that happened. Without a name, a dry run only previews the id
        the next launch would claim, and a real run claims it.
        """
        if config.batch_id is not None:
            batch = run_store.open_batch(self.artifacts.runs, config.batch_id)
            if run_store.read_batch_manifest(batch) is None:
                raise ConfigError(f"unknown batch: {config.batch_id}")
            return batch
        if config.dry_run:
            return run_store.open_batch(
                self.artifacts.runs, run_store.next_batch_id(self.artifacts.runs)
            )
        batch = run_store.create_batch(
            self.artifacts.runs,
            {
                "run_mode": None,
                "pipeline_variant": config.pipeline_variant,
                "command": config.command,
                "config": config.to_dict(),
            },
        )
        config.batch_id = batch.batch_id
        return batch

    def run(self, config: PipelineConfig) -> RunResult:
        validate_config(config)
        run_id = config.run_id or generate_run_id(config.language, config.tasks)
        config.run_id = run_id
        stages = self.stage_sequence(config)
        config_hash = stable_hash(
            config.to_dict(),
            ignored=_CONFIG_HASH_IGNORED_FIELDS,
        )
        batch, paths = self._open_run(config, run_id)
        previous = self.load_previous(paths) if config.resume else {}
        identity = run_identity(config, config_hash)
        run_exists = paths.manifest.exists()
        _reject_unrequested_reuse(paths.root, config, run_id)
        if config.dry_run:
            results = [
                self.plan_stage(name, callback, config, config_hash)
                for name, callback in stages
            ]
            return RunResult(run_id, "dry_run", config.command, results)

        self._initialize_run(batch, paths, identity, run_id, run_exists)
        self._prepare_run_directory(stages, config, paths.root, run_exists)
        results = self._run_stages(stages, config, config_hash, previous, paths)
        return self._finish_run(run_id, config, paths, results)

    def _open_run(
        self, config: PipelineConfig, run_id: str
    ) -> tuple[run_store.BatchPaths, run_store.RunPaths]:
        """The batch and run directory this invocation works in.

        Resolved through the run store first: it validates that ``run_id`` is a
        contained identifier. Deriving the directory here would let a
        traversing id create files before anything checked it, including a
        batch claimed for a run that can never exist. A dry run claims nothing.
        """
        validate_opaque_id(run_id)
        batch = self._batch_for(config)
        paths = run_store.open_run(batch.root, run_id)
        config.run_dir = str(paths.root)
        return batch, paths

    def _initialize_run(
        self,
        batch: run_store.BatchPaths,
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
        run_store.create_run(
            batch.root, run_id, {"batch_id": batch.batch_id, **identity}
        )

    def _prepare_run_directory(
        self,
        stages: list[tuple[str, StageCallable]],
        config: PipelineConfig,
        run_dir: Path,
        run_exists: bool,
    ) -> None:
        """Materialize the engine workspace and, for a new run, its resolved config."""
        if _stages_require_workspace(stages):
            # Execution always uses a run-local engine copy, so runs never
            # share the harness.
            config.engine_dir = str(self.prepare_workspace(run_dir, config.language))
        if not run_exists:
            write_json(run_dir / "config.resolved.yaml", config.to_dict())

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
        """Run, resume or refuse one stage. Also returns whether the run stops."""
        plan = self.plan_stage(name, callback, config, config_hash)
        resumed = self.resume_stage(previous, plan, config)
        if resumed:
            self._record_resumed_stage(name, resumed, config, paths)
            return resumed, False
        if plan.status == "error":
            self._record_stage(paths, plan)
            return plan, config.fail_fast

        result = _execute_stage(name, callback, config, config_hash, plan)
        self.apply_stage_outputs(name, result, config)
        self._record_stage(paths, result)
        return result, config.fail_fast and _is_failed_stage(result)

    def _record_resumed_stage(
        self,
        name: str,
        resumed: StageResult,
        config: PipelineConfig,
        paths: run_store.RunPaths,
    ) -> None:
        self.apply_stage_outputs(name, resumed, config)
        stage_id = contract_stage_id(name)
        run_store.append_event(
            paths,
            "stage_skipped_resume",
            stage=stage_id,
            status=stage_status(stage_id, resumed),
        )

    def _record_stage(self, paths: run_store.RunPaths, result: StageResult) -> None:
        """Record one immutable stage attempt in the run-centric store.

        Recording is shared with the stage service so a run directory reads the
        same whoever wrote it. The runner announces the stage as it records it
        rather than before the work: it also records planning errors, which
        never ran a stage at all.
        """
        stage = contract_stage_id(result.name)
        announce_stage_start(paths, stage)
        record_stage_attempt(paths, stage, result)

    def _finish_run(
        self,
        run_id: str,
        config: PipelineConfig,
        paths: run_store.RunPaths,
        results: list[StageResult],
    ) -> RunResult:
        """Write the run summary, log and finished event."""
        status = run_status(results)
        run_result = RunResult(
            run_id,
            status,
            config.command,
            results,
            str(paths.root.relative_to(REPO_ROOT)),
        )
        write_json(paths.root / "summary.json", run_result.to_dict())
        self.write_log(paths.root, run_result)
        run_store.append_event(paths, "run_finished", run_status=status)
        return run_result

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
        """The ``(internal stage name, callable)`` pairs this invocation runs."""
        callables = self._stage_callables()
        return [(name, callables[name]) for name in self._stage_names(config)]

    def _stage_callables(self) -> dict[str, StageCallable]:
        """Read on every call, so a replaced adapter method is the one used."""
        return {
            EXTRACTION_STAGE_NAME: self.tests.extract,
            TECHNICAL_VALIDATION_STAGE_NAME: self.tests.technical_validation,
            REFERENCE_VALIDATION_STAGE_NAME: self.tests.reference_validation,
            TRANSFORMATION_PARSING_STAGE_NAME: self.parser.parse,
            TRANSFORMATION_VALIDATION_STAGE_NAME: (
                self.transformations.semantic_validation
            ),
        }

    @staticmethod
    def _stage_names(config: PipelineConfig) -> tuple[str, ...]:
        if config.command in _STANDALONE_COMMAND_STAGES:
            return _STANDALONE_COMMAND_STAGES[config.command]
        if config.command == "tests.validate":
            return _TEST_VALIDATION_STAGES.get(
                config.test_validation_stage, _ALL_TEST_VALIDATION_STAGES
            )
        enabled = {
            "technical": config.technical_validation,
            "reference": config.reference_validation,
            "parsing": config.transformation_parsing,
            "semantic": config.semantic_validation,
        }
        start = PIPELINE_STAGES.index(config.start_stage)
        stop = PIPELINE_STAGES.index(config.stop_after)
        return tuple(
            _PIPELINE_STEP_STAGES[step]
            for step in PIPELINE_STAGES[start : stop + 1]
            if enabled.get(step, True)
        )

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
            previous.status in _RESUMABLE_STAGE_STATUSES
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
        return prepare_workspace(run_dir, language)

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


def _latest_execution_attempt(paths: run_store.RunPaths) -> int:
    attempts = existing_attempts(paths.stage_attempts_dir(EXECUTION_STAGE_ID))
    if not attempts:
        raise ConfigError(f"run {paths.root.name} recorded no execution attempt")
    return max(attempts)


def _reject_unrequested_reuse(
    run_dir: Path, config: PipelineConfig, run_id: str
) -> None:
    """Refuse to write into an existing run unless asked to resume or force."""
    if run_dir.exists() and not (config.dry_run or config.resume or config.force):
        raise ConfigError(f"Run already exists: {run_id}. Use --resume or --force.")


def _execute_stage(
    name: str,
    callback: StageCallable,
    config: PipelineConfig,
    config_hash: str,
    plan: StageResult,
) -> StageResult:
    """Run one planned stage. An exception becomes an infrastructure error."""
    try:
        result = callback(config, False)
    except Exception as exc:
        result = infrastructure_error_result(
            name,
            exc,
            input_hash=plan.input_hash,
        )
    result.config_hash = config_hash
    if not result.input_hash:
        result.input_hash = plan.input_hash
    return result


def _is_failed_stage(result: StageResult) -> bool:
    return result.status in _FAILED_STAGE_STATUSES or bool(result.domain_failures)


def run_identity(config: PipelineConfig, config_hash: str) -> dict[str, object]:
    """The immutable manifest fields for a locally started run.

    A run is exactly one combination, so each identity axis must resolve to at
    most one value. An open axis would let a stage select every value and
    produce results the run id cannot account for.
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


def stable_hash(
    payload: dict[str, object],
    ignored: Collection[str] | None = None,
) -> str:
    excluded_fields = ignored or set()
    normalized = {
        key: value for key, value in payload.items() if key not in excluded_fields
    }
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_status(results: list[StageResult]) -> str:
    statuses = [
        stage_status(contract_stage_id(result.name), result) for result in results
    ]
    if any(status == "infrastructure_error" for status in statuses):
        return "failed"
    if any(status == "failed" for status in statuses):
        return "completed_with_failures"
    if any(status == "skipped" for status in statuses):
        return "incomplete"
    return "completed"
