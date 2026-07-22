"""Public CLI contract for all non-n8n experiment workflow stages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from llm4mtl.experiment_runner.config import ConfigError, load_pipeline_config, load_resolved_config, validate_config
from llm4mtl.experiment_runner.models import PipelineConfig, RunResult
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m Experiment_Runner")
    domains = parser.add_subparsers(dest="domain", required=True)

    tests = domains.add_parser("tests", help="Generated-test extraction and validation.")
    test_actions = tests.add_subparsers(dest="action", required=True)
    extract = test_actions.add_parser("extract", help="Extract generated suites from LLM responses.")
    add_language(extract)
    add_task_selection(extract)
    add_test_selection(extract)
    add_execution(extract)
    extract.add_argument("--response", action="append", type=Path)
    extract.add_argument("--suite-id")
    overwrite = extract.add_mutually_exclusive_group()
    overwrite.add_argument("--overwrite", action="store_true")
    overwrite.add_argument("--no-overwrite", action="store_true")

    tests_validate = test_actions.add_parser("validate", help="Technical/reference validation of suites.")
    add_language(tests_validate)
    add_task_selection(tests_validate)
    add_test_selection(tests_validate)
    add_execution(tests_validate)
    tests_validate.add_argument("--stage", choices=("all", "technical", "reference"), default="all")
    tests_validate.add_argument("--suite-id")
    tests_validate.add_argument("--suite", action="append", type=Path)

    transformations = domains.add_parser("transformations", help="Generated transformation checks.")
    transformation_actions = transformations.add_subparsers(dest="action", required=True)
    parse = transformation_actions.add_parser("parse", help="Syntax-check generated transformations.")
    add_language(parse)
    add_task_selection(parse)
    add_transformation_selection(parse)
    add_execution(parse)

    transformations_validate = transformation_actions.add_parser(
        "validate", help="Run validated suites on generated transformations."
    )
    add_language(transformations_validate)
    add_task_selection(transformations_validate)
    add_test_selection(transformations_validate)
    add_transformation_selection(transformations_validate)
    add_execution(transformations_validate)
    transformations_validate.add_argument("--suite-id")
    transformations_validate.add_argument("--suite", action="append", type=Path)

    pipeline = domains.add_parser("pipeline", help="Full experiment pipeline.")
    pipeline_actions = pipeline.add_subparsers(dest="action", required=True)
    pipeline_run = pipeline_actions.add_parser("run", help="Run configured workflow stages.")
    pipeline_run.add_argument("--config", type=Path)
    add_language(pipeline_run, default=None)
    add_task_selection(pipeline_run)
    add_test_selection(pipeline_run)
    add_transformation_selection(pipeline_run)
    add_execution(pipeline_run, defaults_none=True)
    pipeline_run.add_argument("--suite-id")
    pipeline_run.add_argument(
        "--start-stage", choices=("extract", "technical", "reference", "parsing", "semantic")
    )
    pipeline_run.add_argument(
        "--stop-after", choices=("extract", "technical", "reference", "parsing", "semantic")
    )
    return parser


def add_language(parser: argparse.ArgumentParser, default: str | None = "etl") -> None:
    parser.add_argument("--language", choices=("etl",), default=default)


def add_task_selection(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--task", action="append")
    group.add_argument("--all-tasks", action="store_true")


def add_test_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--test-model", action="append")
    parser.add_argument("--test-strategy", action="append")


def add_transformation_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--transformation-model", action="append")
    parser.add_argument("--transformation-strategy", action="append")
    parser.add_argument("--transformation", action="append", type=Path)


def add_execution(parser: argparse.ArgumentParser, defaults_none: bool = False) -> None:
    boolean_default = None if defaults_none else False
    parser.add_argument("--dry-run", action="store_true", default=boolean_default)
    parser.add_argument("--run-id")
    parser.add_argument("--resume", action="store_true", default=boolean_default)
    parser.add_argument("--force", action="store_true", default=boolean_default)
    parser.add_argument("--output-format", choices=("text", "json"), default=None if defaults_none else "text")
    parser.add_argument("--verbose", action="store_true", default=boolean_default)
    parser.add_argument("--keep-workspace", action="store_true", default=boolean_default)
    parser.add_argument("--fail-fast", action="store_true", default=boolean_default)


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    command = f"{args.domain}.{args.action}"
    if command == "pipeline.run" and args.config:
        reject_config_selector_overrides(args)
        config = load_pipeline_config(args.config)
        apply_execution_overrides(config, args)
        config.command = command
        validate_config(config)
        return config
    if command == "pipeline.run" and args.resume and args.run_id and not has_pipeline_selection(args):
        from llm4mtl.paths import TARGET

        resolved = TARGET.runs / args.run_id / "config.resolved.yaml"
        config = load_resolved_config(resolved)
        apply_execution_overrides(config, args)
        config.command = command
        validate_config(config)
        return config

    config = PipelineConfig(
        language=args.language or "etl",
        tasks=list(args.task or []),
        all_tasks=bool(args.all_tasks),
        responses=[str(path) for path in getattr(args, "response", None) or []],
        suites=[str(path) for path in getattr(args, "suite", None) or []],
        transformations=[str(path) for path in getattr(args, "transformation", None) or []],
        test_models=list(getattr(args, "test_model", None) or []),
        test_strategies=list(getattr(args, "test_strategy", None) or []),
        transformation_models=list(getattr(args, "transformation_model", None) or []),
        transformation_strategies=list(getattr(args, "transformation_strategy", None) or []),
        suite_id=getattr(args, "suite_id", None),
        overwrite=bool(getattr(args, "overwrite", False)) and not bool(getattr(args, "no_overwrite", False)),
        test_validation_stage=getattr(args, "stage", "all"),
        start_stage=getattr(args, "start_stage", None) or "extract",
        stop_after=getattr(args, "stop_after", None) or "semantic",
        run_id=args.run_id,
        resume=bool(args.resume),
        force=bool(args.force),
        dry_run=bool(args.dry_run),
        output_format=args.output_format or "text",
        verbose=bool(args.verbose),
        keep_workspace=bool(args.keep_workspace),
        fail_fast=bool(args.fail_fast),
        command=command,
    )
    validate_command_constraints(config)
    validate_config(config)
    return config


def has_pipeline_selection(args: argparse.Namespace) -> bool:
    return any(
        (
            args.task,
            args.all_tasks,
            args.test_model,
            args.test_strategy,
            args.transformation_model,
            args.transformation_strategy,
            args.transformation,
            args.suite_id,
        )
    )


def validate_command_constraints(config: PipelineConfig) -> None:
    if config.command == "tests.extract":
        if config.suite_id and len(config.responses) != 1:
            raise ConfigError("tests extract: --suite-id requires exactly one --response.")
        if config.all_tasks and config.responses:
            raise ConfigError("tests extract: --all-tasks cannot be combined with --response.")
    if config.command == "tests.validate" and config.suite_id and not config.suites:
        require_suite_identity(config)
    if config.command in {"transformations.validate", "pipeline.run"} and config.suite_id and not config.suites:
        require_suite_identity(config)


def require_suite_identity(config: PipelineConfig) -> None:
    if len(config.tasks) != 1 or len(config.test_models) != 1 or len(config.test_strategies) != 1:
        raise ConfigError(
            "--suite-id requires exactly one --task, --test-model, and --test-strategy, "
            "unless --suite PATH is supplied."
        )


def reject_config_selector_overrides(args: argparse.Namespace) -> None:
    selectors = {
        "--language": args.language,
        "--task": args.task,
        "--all-tasks": args.all_tasks,
        "--test-model": args.test_model,
        "--test-strategy": args.test_strategy,
        "--transformation-model": args.transformation_model,
        "--transformation-strategy": args.transformation_strategy,
        "--transformation": args.transformation,
        "--suite-id": args.suite_id,
        "--start-stage": args.start_stage,
        "--stop-after": args.stop_after,
    }
    used = [name for name, value in selectors.items() if value not in (None, False, [])]
    if used:
        raise ConfigError(
            "When --config is used, selector overrides are forbidden: " + ", ".join(used)
        )


def apply_execution_overrides(config: PipelineConfig, args: argparse.Namespace) -> None:
    for name in ("dry_run", "resume", "force", "verbose", "keep_workspace", "fail_fast"):
        value = getattr(args, name)
        if value is not None:
            setattr(config, name, bool(value))
    if args.run_id:
        config.run_id = args.run_id
    if args.output_format:
        config.output_format = args.output_format


def emit_result(result: RunResult, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Run: {result.run_id}")
    print(f"Status: {result.status}")
    for stage in result.stages:
        counts = " ".join(f"{key}={value}" for key, value in stage.counts.items())
        print(f"{stage.name}: {stage.status} {counts}".rstrip())
        if stage.status == "dry_run" and stage.name == "transformation_validation":
            print(f"Selected validated suites: {stage.counts.get('selected_suites', 0)}")
            print(f"Selected transformations: {stage.counts.get('selected_transformations', 0)}")
            print(f"Execution pairs: {stage.counts.get('execution_pairs', 0)}")
            for pair in stage.details.get("pairs", []):
                print(pair)
        results_file = stage.details.get("results_file")
        if results_file:
            print(f"Results: {results_file}")
        for artifact in stage.details.get("artifacts", []):
            print(f"{artifact['status']}: {artifact['path']}")
    if result.run_dir:
        print(f"Run metadata: {result.run_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = config_from_args(args)
        result = ExperimentOrchestrator().run(config)
        emit_result(result, config.output_format)
        return 0 if result.status in {"completed", "dry_run"} else 1
    except ConfigError as exc:
        output_format = getattr(args, "output_format", None) or "text"
        if output_format == "json":
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        output_format = getattr(args, "output_format", None) or "text"
        payload = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
        if output_format == "json":
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"Error: {payload['error']}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
