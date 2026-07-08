"""Response discovery and path-to-suite metadata inference."""

from __future__ import annotations

import argparse
from pathlib import Path

from etl.extraction.models import ResponseTarget


SMOKE_RESPONSE_SUFFIXES = (".qwen-smoke",)


def discover_responses(args: argparse.Namespace) -> list[ResponseTarget]:
    if args.response:
        if args.suite_id and len(args.response) != 1:
            raise SystemExit("--suite-id can only be used with a single --response")
        return [
            response_target_from_path(
                response_path=path.resolve(),
                responses_root=args.responses_root.resolve(),
                llm_override=args.llm,
                strategy_override=args.strategy,
                task_override=args.task,
            )
            for path in args.response
        ]

    root = args.responses_root.resolve()
    pattern = f"*/**/{args.task}.md" if args.task else "*/*/*.md"
    responses = sorted(
        path for path in root.glob(pattern) if path.is_file() and not path.name.startswith(".")
    )
    return [
        response_target_from_path(
            response_path=path,
            responses_root=root,
            llm_override=None,
            strategy_override=None,
            task_override=args.task,
        )
        for path in responses
    ]


def response_target_from_path(
    response_path: Path,
    responses_root: Path,
    llm_override: str | None,
    strategy_override: str | None,
    task_override: str | None,
) -> ResponseTarget:
    task = task_override or task_name_from_response(response_path)
    if task_override and task_name_from_response(response_path) != task_override:
        raise SystemExit(f"Expected response file named {task_override}.md: {response_path}")

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
        raise SystemExit(
            "Could not infer llm/strategy from response path. Provide --llm and "
            f"--strategy for {response_path}"
        )

    return ResponseTarget(
        response_path=response_path,
        llm=llm,
        strategy=strategy,
        task=task,
    )


def task_name_from_response(response_path: Path) -> str:
    stem = response_path.stem
    for suffix in SMOKE_RESPONSE_SUFFIXES:
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem
