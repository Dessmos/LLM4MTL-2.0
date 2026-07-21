"""YAML/JSON experiment configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from llm4mtl.experiment_runner.models import PipelineConfig


ALLOWED_MODELS = {"gpt-5", "claude-sonnet-4", "gemini-2-5-pro"}
ALLOWED_STRATEGIES = {"only_prompt", "few_shot", "grammar", "few_shots_AND_grammar"}
PIPELINE_STAGES = ("extract", "technical", "reference", "parsing", "semantic")


class ConfigError(ValueError):
    pass


def load_pipeline_config(path: Path) -> PipelineConfig:
    payload = load_mapping(path)
    test_suites = mapping(payload.get("test_suites"))
    extraction = mapping(test_suites.get("extraction"))
    validation = mapping(test_suites.get("validation"))
    transformations = mapping(payload.get("transformations"))
    execution = mapping(payload.get("execution"))

    config = PipelineConfig(
        language=str(payload.get("language", "etl")),
        tasks=string_list(payload.get("tasks")),
        all_tasks=bool(payload.get("all_tasks", False)),
        test_models=string_list(test_suites.get("models")),
        test_strategies=string_list(test_suites.get("strategies")),
        transformation_models=string_list(transformations.get("models")),
        transformation_strategies=string_list(transformations.get("strategies")),
        overwrite=bool(extraction.get("overwrite", False)),
        technical_validation=bool(validation.get("technical", True)),
        reference_validation=bool(validation.get("reference", True)),
        transformation_parsing=bool(transformations.get("parse", True)),
        semantic_validation=bool(transformations.get("semantic_validation", True)),
        start_stage=str(execution.get("start_stage", "extract")),
        stop_after=str(execution.get("stop_after", "semantic")),
        resume=bool(execution.get("resume", False)),
        force=bool(execution.get("force", False)),
        dry_run=bool(execution.get("dry_run", False)),
        output_format=str(execution.get("output_format", "text")),
        verbose=bool(execution.get("verbose", False)),
        keep_workspace=bool(execution.get("keep_workspace", False)),
        fail_fast=bool(execution.get("fail_fast", False)),
        run_id=string_or_none(execution.get("run_id")),
    )
    if extraction.get("enabled") is False and config.start_stage == "extract":
        config.start_stage = "technical"
    validate_config(config)
    return config


def load_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Experiment config not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        value = json.loads(text)
    else:
        try:
            import yaml  # type: ignore

            value = yaml.safe_load(text)
        except ImportError:
            value = parse_simple_yaml(text)
    if not isinstance(value, dict):
        raise ConfigError("Experiment config must contain a mapping at the top level.")
    return value


def load_resolved_config(path: Path) -> PipelineConfig:
    payload = load_mapping(path)
    allowed = {item.name for item in fields(PipelineConfig)}
    return PipelineConfig(**{key: value for key, value in payload.items() if key in allowed})


def validate_config(config: PipelineConfig, require_selection: bool = True) -> None:
    if config.language.lower() != "etl":
        raise ConfigError(f"Unsupported language: {config.language}. Currently only etl is supported.")
    if config.tasks and config.all_tasks:
        raise ConfigError("--task and --all-tasks are mutually exclusive.")
    if require_selection and not config.tasks and not config.all_tasks and not any(
        (config.responses, config.suites, config.transformations)
    ):
        raise ConfigError("Select at least one --task, use --all-tasks, or provide an explicit input path.")
    unknown_models = (
        set(config.test_models) | set(config.transformation_models)
    ) - ALLOWED_MODELS
    if unknown_models:
        raise ConfigError(f"Unsupported model(s): {', '.join(sorted(unknown_models))}")
    unknown_strategies = (
        set(config.test_strategies) | set(config.transformation_strategies)
    ) - ALLOWED_STRATEGIES
    if unknown_strategies:
        raise ConfigError(f"Unsupported strategy/strategies: {', '.join(sorted(unknown_strategies))}")
    if config.start_stage not in PIPELINE_STAGES:
        raise ConfigError(f"Unknown start stage: {config.start_stage}")
    if config.stop_after not in PIPELINE_STAGES:
        raise ConfigError(f"Unknown stop stage: {config.stop_after}")
    if PIPELINE_STAGES.index(config.start_stage) > PIPELINE_STAGES.index(config.stop_after):
        raise ConfigError("--start-stage must not come after --stop-after.")


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the mapping/list/scalar YAML subset used by experiment configs."""

    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        is_list = lines[index][1].startswith("- ") or lines[index][1] == "-"
        container: Any = [] if is_list else {}
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise ConfigError(f"Unexpected indentation near: {content}")
            if is_list:
                if not content.startswith("-"):
                    break
                item_text = content[1:].strip()
                if not item_text:
                    if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
                        container.append(None)
                        index += 1
                    else:
                        item, index = parse_block(index + 1, lines[index + 1][0])
                        container.append(item)
                    continue
                if ":" in item_text:
                    key, value_text = split_key_value(item_text)
                    item = {key: parse_scalar(value_text)} if value_text else {key: None}
                    index += 1
                    if index < len(lines) and lines[index][0] > indent:
                        child, index = parse_block(index, lines[index][0])
                        if value_text:
                            if isinstance(child, dict):
                                item.update(child)
                        else:
                            item[key] = child
                    container.append(item)
                else:
                    container.append(parse_scalar(item_text))
                    index += 1
            else:
                if content.startswith("-"):
                    break
                key, value_text = split_key_value(content)
                index += 1
                if value_text:
                    container[key] = parse_scalar(value_text)
                elif index < len(lines) and lines[index][0] > indent:
                    child, index = parse_block(index, lines[index][0])
                    container[key] = child
                else:
                    container[key] = {}
        return container, index

    if not lines:
        return {}
    result, index = parse_block(0, lines[0][0])
    if index != len(lines) or not isinstance(result, dict):
        raise ConfigError("Unsupported YAML structure.")
    return result


def split_key_value(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise ConfigError(f"Expected key: value, got: {text}")
    key, value = text.split(":", 1)
    return key.strip(), value.strip()


def parse_scalar(value: str) -> Any:
    if not value:
        return None
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if value.startswith("[") or value.startswith("{"):
        return json.loads(value.replace("'", '"'))
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def string_or_none(value: Any) -> str | None:
    return None if value is None else str(value)
