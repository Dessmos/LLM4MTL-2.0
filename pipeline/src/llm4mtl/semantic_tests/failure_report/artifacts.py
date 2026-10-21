"""Reading the recorded artifacts a report cites.

Every artifact enters a report the same way: as a repository-relative path, its
content hash where one is meaningful, and either its text or a bounded excerpt.
Nothing here interprets what it read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.paths import require_repository_relative
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.models import (
    EXECUTION_LOG_EXCERPT_CHARS,
    EXECUTION_LOG_EXCERPT_LINES,
    MAVEN_BUNDLE_LINES,
)
from llm4mtl.serialization.hashing import file_sha256
from llm4mtl.serialization.json_io import read_json


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(f"cannot read {label} from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FailureReportError(f"{label} must contain one JSON object")
    return payload


def _log_excerpt(path: Path) -> dict[str, Any]:
    """A bounded citation of one build log.

    The excerpt is the log's tail, copied as is. ``path`` and ``sha256`` name
    the full log, and ``truncated`` says whether the excerpt is the whole file.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise FailureReportError(f"cannot read evidence file {path}: {exc}") from exc
    lines = content.splitlines()
    excerpt = "\n".join(lines[-EXECUTION_LOG_EXCERPT_LINES:])
    if len(excerpt) > EXECUTION_LOG_EXCERPT_CHARS:
        excerpt = excerpt[-EXECUTION_LOG_EXCERPT_CHARS:]
    return {
        "path": _repository_path(path),
        "sha256": file_sha256(path),
        "lines": len(lines),
        "excerpt": excerpt,
        "excerpt_lines": excerpt.count("\n") + 1 if excerpt else 0,
        "truncated": excerpt != content.rstrip("\n"),
    }


def _optional_log_excerpt(path: Path | None) -> dict[str, Any] | None:
    """:func:`_log_excerpt` of ``path``, or ``None`` when no log was recorded."""
    return _log_excerpt(path) if path is not None else None


def _text_artifact(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FailureReportError(
            f"cannot read UTF-8 evidence file {path}: {exc}"
        ) from exc
    return {
        "path": _repository_path(path),
        "sha256": file_sha256(path),
        "content": content,
    }


def _json_artifact(path: Path) -> dict[str, Any]:
    artifact = _text_artifact(path)
    try:
        artifact["document"] = json.loads(artifact["content"])
    except json.JSONDecodeError as exc:
        raise FailureReportError(f"invalid JSON evidence file {path}: {exc}") from exc
    return artifact


def _suite_artifact_path(suite_dir: Path, raw_path: object, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise FailureReportError(f"{label} path must be a non-empty string")
    candidate = (suite_dir / raw_path).resolve()
    try:
        candidate.relative_to(suite_dir.resolve())
    except ValueError as exc:
        raise FailureReportError(
            f"{label} escapes the generated suite: {raw_path}"
        ) from exc
    if not candidate.is_file():
        raise FailureReportError(f"{label} does not exist: {raw_path}")
    return candidate


def _relevant_log_lines(cited_log: dict[str, Any] | None) -> dict[str, Any] | None:
    """The build-log lines that say something about this run's outcome.

    A Maven log is mostly build progress. The useful lines are the ones Maven
    itself marked: errors, warnings, the Surefire summary, the build result.
    Filtering on those markers judges nothing about the failure. The report
    keeps the wider excerpt and the archive keeps the full log.
    """
    if cited_log is None:
        return None
    lines = [
        line
        for line in cited_log["excerpt"].splitlines()
        if line.startswith(("[ERROR]", "[WARNING]"))
        or "Tests run:" in line
        or "BUILD " in line
    ]
    return {
        "path": cited_log["path"],
        "lines": cited_log["lines"],
        "selected": "marked lines only; the full log is at `path`",
        "excerpt": "\n".join(lines[-MAVEN_BUNDLE_LINES:]),
    }


def _cited(artifact: dict[str, Any]) -> dict[str, Any]:
    """One artifact as the prompt needs it: where it is and what is in it."""
    return {"path": artifact["path"], "content": artifact["content"]}


def _repository_path(path: Path) -> str:
    """``path`` relative to the repository, or :class:`FailureReportError`.

    A report that cited a path outside the repository would be unreadable to
    anyone else, so that case becomes the error the builders already handle.
    """
    try:
        return require_repository_relative(path)
    except ValueError as exc:
        raise FailureReportError(f"path escapes the repository: {path}") from exc
