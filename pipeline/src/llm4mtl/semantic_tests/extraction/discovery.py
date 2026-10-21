"""Response identity read from a response path and explicit overrides."""

from __future__ import annotations

from pathlib import Path

from llm4mtl.semantic_tests.extraction.models import (
    ResponseSelectionError,
    ResponseTarget,
)


SMOKE_RESPONSE_SUFFIXES = (".qwen-smoke",)


def response_target_from_path(
    response_path: Path,
    responses_root: Path,
    llm_override: str | None,
    strategy_override: str | None,
    task_override: str | None,
) -> ResponseTarget:
    """Resolve response identity from its path and explicit overrides."""
    task = task_override or task_name_from_response(response_path)
    if task_override and task_name_from_response(response_path) != task_override:
        raise ResponseSelectionError(
            f"Expected response file named {task_override}.md: {response_path}"
        )

    llm = llm_override
    strategy = strategy_override

    try:
        rel = response_path.relative_to(responses_root)
    except ValueError:
        rel = None

    if rel and len(rel.parts) >= 3:
        llm = llm or rel.parts[0]
        strategy = strategy or rel.parts[1]

    if not llm or not strategy:
        raise ResponseSelectionError(
            "Could not infer llm/strategy from response path, and none was "
            f"given explicitly: {response_path}"
        )

    return ResponseTarget(
        response_path=response_path,
        llm=llm,
        strategy=strategy,
        task=task,
    )


def task_name_from_response(response_path: Path) -> str:
    """Return the task name encoded by a response filename."""
    stem = response_path.stem
    for suffix in SMOKE_RESPONSE_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem
