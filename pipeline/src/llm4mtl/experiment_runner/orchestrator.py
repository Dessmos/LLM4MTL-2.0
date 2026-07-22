"""Application-level ordering, state, resume, and summary orchestration."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from llm4mtl.experiment_runner.adapters.test_generation import TestGenerationAdapter
from llm4mtl.experiment_runner.adapters.transformation_parser import TransformationParserAdapter
from llm4mtl.experiment_runner.adapters.transformation_validation import TransformationValidationAdapter
from llm4mtl.experiment_runner.config import PIPELINE_STAGES, ConfigError, validate_config
from llm4mtl.experiment_runner.models import PipelineConfig, RunResult, StageResult
from llm4mtl import run_store
from llm4mtl.paths import REPO_ROOT, TARGET


StageCallable = Callable[[PipelineConfig, bool], StageResult]


class ExperimentOrchestrator:
    def __init__(self, repo_root: Path | None = None) -> None:
        # Adapter subprocesses use this path as their cwd. After the v5 migration
        # every active component lives below the repository root.
        self.repo_root = (repo_root or REPO_ROOT).resolve()
        # v5 migration (Stage 4): runs are now run-centric under artifacts/work/runs.
        self.runs_root = TARGET.runs
        self.tests = TestGenerationAdapter(self.repo_root)
        self.parser = TransformationParserAdapter(self.repo_root)
        self.transformations = TransformationValidationAdapter(self.repo_root)

    def run(self, config: PipelineConfig) -> RunResult:
        validate_config(config)
        run_id = config.run_id or generate_run_id(config)
        config.run_id = run_id
        stages = self.stage_sequence(config)
        config_hash = stable_hash(
            config.to_dict(),
            ignored={"resume", "force", "dry_run", "verbose", "output_format", "etl_test_dir"},
        )
        run_dir = self.runs_root / run_id
        previous = self.load_previous(run_dir) if config.resume else {}

        if run_dir.exists() and not config.dry_run and not config.resume and not config.force:
            raise ConfigError(f"Run already exists: {run_id}. Use --resume or --force.")

        if config.dry_run:
            results = [self.plan_stage(name, callback, config, config_hash) for name, callback in stages]
            return RunResult(run_id, "dry_run", config.command, results)

        run_dir.mkdir(parents=True, exist_ok=True)
        if config.keep_workspace:
            config.etl_test_dir = str(self.prepare_workspace(run_dir))
        write_json(run_dir / "config.resolved.yaml", config.to_dict())
        paths = run_store.open_run(self.runs_root, run_id)
        if config.resume and paths.manifest.exists():
            run_store.append_event(paths, "run_resumed")
        else:
            run_store.create_run(
                self.runs_root,
                run_id,
                {
                    "command": config.command,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "config_hash": config_hash,
                },
                force=True,
            )

        results: list[StageResult] = []
        for name, callback in stages:
            plan = self.plan_stage(name, callback, config, config_hash)
            resumed = self.resume_stage(previous.get(name), plan, config)
            if resumed:
                results.append(resumed)
                self.apply_stage_outputs(name, resumed, config)
                self.persist_progress(run_dir, results)
                run_store.append_event(paths, "stage_skipped_resume", stage=name, status=resumed.status)
                continue
            if plan.status == "error":
                plan.config_hash = config_hash
                results.append(plan)
                self.persist_progress(run_dir, results)
                self._record_stage(paths, plan)
                if config.fail_fast:
                    break
                continue

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
            results.append(result)
            self.apply_stage_outputs(name, result, config)
            self.persist_progress(run_dir, results)
            self._record_stage(paths, result)
            if config.fail_fast and (
                result.status in {"error", "infrastructure_error"} or result.domain_failures
            ):
                break

        status = run_status(results)
        run_result = RunResult(run_id, status, config.command, results, str(run_dir.relative_to(REPO_ROOT)))
        write_json(run_dir / "summary.json", run_result.to_dict())
        self.write_log(run_dir, run_result)
        run_store.append_event(paths, "run_finished", status=status)
        return run_result

    def _record_stage(self, paths: run_store.RunPaths, result: StageResult) -> None:
        """Record one stage outcome in the run-centric store (immutable attempt + latest)."""
        run_store.append_event(paths, "stage_started", stage=result.name)
        attempt = run_store.record_attempt(paths, result.name, result.to_dict())
        run_store.append_event(
            paths, "stage_finished", stage=result.name, status=result.status, attempt=attempt
        )

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
            return [("transformation_validation", self.transformations.semantic_validation)]

        stage_map: dict[str, tuple[str, StageCallable]] = {
            "extract": ("extraction", self.tests.extract),
            "technical": ("technical_validation", self.tests.technical_validation),
            "reference": ("reference_validation", self.tests.reference_validation),
            "parsing": ("transformation_parsing", self.parser.parse),
            "semantic": ("transformation_validation", self.transformations.semantic_validation),
        }
        start = PIPELINE_STAGES.index(config.start_stage)
        stop = PIPELINE_STAGES.index(config.stop_after)
        selected = []
        for stage in PIPELINE_STAGES[start : stop + 1]:
            if stage == "technical" and not config.technical_validation:
                continue
            if stage == "reference" and not config.reference_validation:
                continue
            if stage == "parsing" and not config.transformation_parsing:
                continue
            if stage == "semantic" and not config.semantic_validation:
                continue
            selected.append(stage_map[stage])
        return selected

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
            previous.details = {**previous.details, "resume_reason": "matching config and input hashes"}
            return previous
        return None

    def load_previous(self, run_dir: Path) -> dict[str, dict[str, object]]:
        path = run_dir / "stage_results.json"
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def persist_progress(self, run_dir: Path, results: list[StageResult]) -> None:
        write_json(run_dir / "stage_results.json", {result.name: result.to_dict() for result in results})

    def prepare_workspace(self, run_dir: Path) -> Path:
        # v5 migration (Stage 2): the ETL test-harness engine moved to engines/etl/harness.
        from llm4mtl.paths import TARGET

        source = TARGET.engine_harness("etl")
        destination = run_dir / "workspace" / "ETL_Test"
        if destination.exists():
            return destination
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("target", ".git", "*.class"),
        )
        return destination

    def write_log(self, run_dir: Path, result: RunResult) -> None:
        lines = [f"run_id={result.run_id}", f"status={result.status}", f"command={result.command}"]
        for stage in result.stages:
            lines.append(f"{stage.name}: status={stage.status} counts={json.dumps(stage.counts, sort_keys=True)}")
            stdout = stage.details.get("stdout")
            stderr = stage.details.get("stderr")
            if stdout:
                lines.append(str(stdout).rstrip())
            if stderr:
                lines.append(str(stderr).rstrip())
        (run_dir / "runner.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_run_id(config: PipelineConfig) -> str:
    task = config.tasks[0].lower() if len(config.tasks) == 1 else "all"
    # Microseconds prevent two requests for the same task in one second from
    # sharing a run directory. Explicit IDs are still protected by the store.
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{config.language}-{task}-{timestamp}"


def stable_hash(payload: dict[str, object], ignored: set[str] | None = None) -> str:
    normalized = {key: value for key, value in payload.items() if key not in (ignored or set())}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_status(results: list[StageResult]) -> str:
    if any(result.status in {"error", "infrastructure_error"} for result in results):
        return "failed"
    if any(result.domain_failures for result in results):
        return "completed_with_failures"
    return "completed"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
