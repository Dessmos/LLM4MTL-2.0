"""Candidate suite discovery shared by validation stages."""

from __future__ import annotations

import argparse
from pathlib import Path

from llm4mtl.semantic_tests.suites.models import CandidateSuite


def discover_suites(args: argparse.Namespace) -> list[CandidateSuite]:
    if args.suite:
        return [suite_from_path(path.resolve(), args.generated_tests_root.resolve()) for path in args.suite]

    root = args.generated_tests_root.resolve()
    task_dirs = [root / args.task] if args.task else sorted(path for path in root.iterdir() if path.is_dir())
    suites: list[CandidateSuite] = []
    for task_dir in task_dirs:
        candidates = task_dir / "candidates"
        if not candidates.exists():
            continue
        for suite_dir in sorted(candidates.glob("*/*/suite_*")):
            if suite_dir.is_dir():
                suites.append(suite_from_path(suite_dir.resolve(), root))
    return suites


def suite_from_path(path: Path, generated_tests_root: Path) -> CandidateSuite:
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

    return CandidateSuite(path=path, task=task, llm=llm, strategy=strategy, suite_id=suite_id)
