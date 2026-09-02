"""YAML/JSON experiment configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.run_store.identity import RUN_ID_PATTERN


ALLOWED_MODELS = {"gpt-5", "claude-sonnet-4", "gemini-2-5-pro"}
ALLOWED_STRATEGIES = {"only_prompt", "few_shot", "grammar", "few_shots_AND_grammar"}
PIPELINE_STAGES = ("extract", "technical", "reference", "parsing", "semantic")
_YamlLine = tuple[int, str]


class ConfigError(ValueError):
    """Raised when an experiment configuration violates the run contract."""


def load_pipeline_config(path: Path) -> PipelineConfig:
    """Load and validate a human-authored pipeline configuration."""
    payload = load_mapping(path)
    language = payload.get("language")
    if not isinstance(language, str) or not language.strip():
        raise ConfigError("Experiment config must declare a non-empty language.")
    test_suites = mapping(payload.get("test_suites"))
    extraction = mapping(test_suites.get("extraction"))
    validation = mapping(test_suites.get("validation"))
    transformations = mapping(payload.get("transformations"))
    execution = mapping(payload.get("execution"))

    config = PipelineConfig(
        language=language,
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
    """Load a top-level mapping from a JSON or supported YAML file."""
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
    """Load the persisted fields understood by the current runner version."""
    payload = load_mapping(path)
    allowed = {item.name for item in fields(PipelineConfig)}
    known_values = {key: value for key, value in payload.items() if key in allowed}
    return PipelineConfig(**known_values)


def validate_config(config: PipelineConfig, require_selection: bool = True) -> None:
    """Validate identity, selection, and stage-range constraints."""
    # The language must have an adapter. Rejecting here rather than deep in a
    # stage keeps an unimplemented language from producing partial artifacts
    # attributed to a language that never ran.
    from llm4mtl.languages import (
        REQUIRED_LANGUAGES,
        UnsupportedLanguageError,
        language_adapter,
    )

    if not isinstance(config.language, str) or not config.language.strip():
        raise ConfigError("A run must declare a non-empty language.")
    if config.suite_id and not RUN_ID_PATTERN.fullmatch(config.suite_id):
        raise ConfigError(
            f"Invalid suite id {config.suite_id!r}: expected a non-empty "
            f"{RUN_ID_PATTERN.pattern} identifier."
        )
    try:
        language_adapter(config.language)
    except UnsupportedLanguageError as exc:
        raise ConfigError(
            f"Unsupported language: {config.language}. "
            f"The thesis requires {', '.join(REQUIRED_LANGUAGES)}; {exc}"
        ) from exc
    if config.all_tasks or len(config.tasks) != 1:
        raise ConfigError(
            "A run must fix exactly one task. Expand several or all tasks through "
            "an experiment matrix so each task receives its own run identity."
        )
    _validate_selections(config)
    _validate_stage_range(config)


def _validate_selections(config: PipelineConfig) -> None:
    """Validate model and strategy selections in their established order."""
    unknown_models = (
        set(config.test_models) | set(config.transformation_models)
    ) - ALLOWED_MODELS
    if unknown_models:
        raise ConfigError(f"Unsupported model(s): {', '.join(sorted(unknown_models))}")
    unknown_strategies = (
        set(config.test_strategies) | set(config.transformation_strategies)
    ) - ALLOWED_STRATEGIES
    if unknown_strategies:
        raise ConfigError(
            "Unsupported strategy/strategies: "
            f"{', '.join(sorted(unknown_strategies))}"
        )


def _validate_stage_range(config: PipelineConfig) -> None:
    """Validate the configured pipeline interval and its direction."""
    if config.start_stage not in PIPELINE_STAGES:
        raise ConfigError(f"Unknown start stage: {config.start_stage}")
    if config.stop_after not in PIPELINE_STAGES:
        raise ConfigError(f"Unknown stop stage: {config.stop_after}")
    start_index = PIPELINE_STAGES.index(config.start_stage)
    stop_index = PIPELINE_STAGES.index(config.stop_after)
    if start_index > stop_index:
        raise ConfigError("--start-stage must not come after --stop-after.")


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the mapping/list/scalar YAML subset used by experiment configs."""
    lines = _simple_yaml_lines(text)
    if not lines:
        return {}
    result, index = _parse_yaml_block(lines, 0, lines[0][0])
    if index != len(lines) or not isinstance(result, dict):
        raise ConfigError("Unsupported YAML structure.")
    return result


def _simple_yaml_lines(text: str) -> list[_YamlLine]:
    lines: list[_YamlLine] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, stripped))
    return lines


def _parse_yaml_block(
    lines: list[_YamlLine], index: int, indent: int
) -> tuple[Any, int]:
    is_list = lines[index][1].startswith("- ") or lines[index][1] == "-"
    if is_list:
        return _parse_yaml_list_block(lines, index, indent)
    return _parse_yaml_mapping_block(lines, index, indent)


def _parse_yaml_list_block(
    lines: list[_YamlLine], index: int, indent: int
) -> tuple[list[Any], int]:
    container: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"Unexpected indentation near: {content}")
        if not content.startswith("-"):
            break
        index = _parse_yaml_list_item(lines, index, indent, container)
    return container, index


def _parse_yaml_mapping_block(
    lines: list[_YamlLine], index: int, indent: int
) -> tuple[dict[str, Any], int]:
    container: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ConfigError(f"Unexpected indentation near: {content}")
        if content.startswith("-"):
            break
        index = _parse_yaml_mapping_item(lines, index, indent, container)
    return container, index


def _parse_yaml_list_item(
    lines: list[_YamlLine],
    index: int,
    indent: int,
    container: list[Any],
) -> int:
    item_text = lines[index][1][1:].strip()
    if not item_text:
        if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
            container.append(None)
            return index + 1
        item, next_index = _parse_yaml_block(lines, index + 1, lines[index + 1][0])
        container.append(item)
        return next_index
    if ":" not in item_text:
        container.append(parse_scalar(item_text))
        return index + 1

    return _parse_yaml_mapping_list_item(
        lines,
        index,
        indent,
        container,
        item_text,
    )


def _parse_yaml_mapping_list_item(
    lines: list[_YamlLine],
    index: int,
    indent: int,
    container: list[Any],
    item_text: str,
) -> int:
    """Parse one list item that starts with a mapping entry."""

    key, value_text = split_key_value(item_text)
    item = {key: parse_scalar(value_text)} if value_text else {key: None}
    index += 1
    if index < len(lines) and lines[index][0] > indent:
        child, index = _parse_yaml_block(lines, index, lines[index][0])
        if value_text and isinstance(child, dict):
            item.update(child)
        elif not value_text:
            item[key] = child
    container.append(item)
    return index


def _parse_yaml_mapping_item(
    lines: list[_YamlLine],
    index: int,
    indent: int,
    container: dict[str, Any],
) -> int:
    key, value_text = split_key_value(lines[index][1])
    index += 1
    if value_text:
        container[key] = parse_scalar(value_text)
    elif index < len(lines) and lines[index][0] > indent:
        child, index = _parse_yaml_block(lines, index, lines[index][0])
        container[key] = child
    else:
        container[key] = {}
    return index


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
