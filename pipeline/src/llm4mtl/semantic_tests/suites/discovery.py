"""Candidate suite discovery shared by validation stages.

A candidate suite lives at ``<task>/candidates/<llm>/<strategy>/<suite_id>``
below a language's generated-tests root. That layout is read in exactly one
place, :func:`candidate_identity`; every selection filter and every pairing rule
asks it instead of counting path components of its own.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from llm4mtl.domain import GeneratedSuite

CANDIDATES_DIRECTORY = "candidates"


@dataclass(frozen=True)
class CandidateIdentity:
    """The identity a candidate suite directory encodes in its own path."""

    task: str
    llm: str
    strategy: str
    suite_id: str


def candidate_identity(path: Path) -> CandidateIdentity:
    """Read ``<task>/candidates/<llm>/<strategy>/<suite_id>`` off the end of ``path``.

    Raises :class:`ValueError` when the path does not end in that shape.
    """
    parts = Path(path).parts
    if len(parts) < 5 or parts[-4] != CANDIDATES_DIRECTORY:
        raise ValueError(
            "not a candidate suite directory "
            f"(<task>/{CANDIDATES_DIRECTORY}/<llm>/<strategy>/<suite_id>): {path}"
        )
    return CandidateIdentity(
        task=parts[-5], llm=parts[-3], strategy=parts[-2], suite_id=parts[-1]
    )


def matches_selection(
    identity: CandidateIdentity,
    *,
    tasks: set[str],
    models: set[str],
    strategies: set[str],
    all_tasks: bool,
    suite_id: str | None,
) -> bool:
    """Whether a candidate belongs to the selection a stage was asked to judge."""
    if identity.llm not in models or identity.strategy not in strategies:
        return False
    if not all_tasks and identity.task not in tasks:
        return False
    return not suite_id or identity.suite_id == suite_id


def candidate_suite_directories(generated_tests_root: Path) -> list[Path]:
    """Return every candidate suite directory, regardless of its opaque id.

    Explicit suite ids are allowed to use the same one-component syntax as run
    ids. They are not required to start with ``suite_``; n8n deliberately uses
    the run id plus an attempt suffix so every generated suite stays attributable
    to its run.
    """
    root = generated_tests_root.resolve()
    return sorted(
        path.resolve()
        for path in root.glob(f"*/{CANDIDATES_DIRECTORY}/*/*/*")
        if path.is_dir()
    )


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
    return [
        suite_from_path(suite_dir.resolve(), generated_tests_root, language)
        for suite_dir in candidate_suite_directories(generated_tests_root)
        if candidate_identity(suite_dir).task == task_dir.name
    ]


def suite_from_path(
    path: Path,
    generated_tests_root: Path,
    language: str,
) -> GeneratedSuite:
    """Build a suite identity from its candidate-directory path.

    ``generated_tests_root`` is kept for the callers that already pass it; the
    identity is read off the path itself, so a suite is spelled the same whether
    or not it lies below the root it was discovered from.
    """
    try:
        identity = candidate_identity(path)
    except ValueError as exc:
        raise SystemExit(
            f"Cannot infer task/llm/strategy/suite_id from {path}"
        ) from exc
    return GeneratedSuite(
        language=language,
        path=path,
        task=identity.task,
        llm=identity.llm,
        strategy=identity.strategy,
        suite_id=identity.suite_id,
    )
