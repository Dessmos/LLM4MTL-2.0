"""Candidate suite discovery shared by validation stages."""

from __future__ import annotations

import argparse
from pathlib import Path

from llm4mtl.domain import GeneratedSuite


def discover_suites(args: argparse.Namespace, language: str) -> list[GeneratedSuite]:
    """Discover candidate suites selected by validation CLI arguments."""
    root = args.generated_tests_root.resolve()
    if args.suite:
        return [
            suite_from_path(
                path.resolve(),
                root,
                language,
            )
            for path in args.suite
        ]

    if args.task:
        task_dirs = [root / args.task]
    else:
        task_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    suites: list[GeneratedSuite] = []
    for task_dir in task_dirs:
        suites.extend(_discover_task_suites(task_dir, root, language))
    return suites


def _discover_task_suites(
    task_dir: Path,
    generated_tests_root: Path,
    language: str,
) -> list[GeneratedSuite]:
    candidates = task_dir / "candidates"
    if not candidates.exists():
        return []
    return [
        suite_from_path(suite_dir.resolve(), generated_tests_root, language)
        for suite_dir in sorted(candidates.glob("*/*/suite_*"))
        if suite_dir.is_dir()
    ]


def suite_from_path(
    path: Path,
    generated_tests_root: Path,
    language: str,
) -> GeneratedSuite:
    """Build a suite identity from its candidate-directory path."""
    try:
        rel = path.relative_to(generated_tests_root)
    except ValueError:
        rel = None

    if rel and len(rel.parts) >= 5 and rel.parts[1] == "candidates":
        task, _, llm, strategy, suite_id = rel.parts[:5]
    else:
        # Expected suffix: <task>/candidates/<llm>/<strategy>/<suite_id>
        parts = path.parts
        try:
            idx = parts.index("candidates")
            task = parts[idx - 1]
            llm = parts[idx + 1]
            strategy = parts[idx + 2]
            suite_id = parts[idx + 3]
        except (ValueError, IndexError):
            raise SystemExit(f"Cannot infer task/llm/strategy/suite_id from {path}")

    return GeneratedSuite(
        language=language,
        path=path,
        task=task,
        llm=llm,
        strategy=strategy,
        suite_id=suite_id,
    )
