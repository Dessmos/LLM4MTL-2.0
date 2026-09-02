"""The request documents, and the containment rules their paths must obey.

A request names files by repository-relative path. Every input must stay inside
the repository and the output under ``artifacts/work``, because a report is
evidence about one run and must not be assembled from — or written to —
anything outside the tree that run was recorded in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.execution_evidence import archived_execution_evidence
from llm4mtl.semantic_tests.failure_report.models import (
    CASE_REQUEST_FIELDS,
    DIFF_FIELDS,
    PAIR_REQUEST_FIELDS,
)
from llm4mtl.serialization.json_io import read_json


@dataclass(frozen=True)
class ReportRequest:
    """Validated paths and selectors for one report assembly."""

    run_manifest: Path
    syntax_evidence: Path
    execution_evidence: Path
    generated_execution: Path
    reference_execution: Path | None
    test_case_id: str
    assertion_id: str | None
    attempt: int
    actual_target_models: tuple[Path, ...]
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None
    actual_vs_expected: dict[str, list[Any]] | None

    @classmethod
    def from_payload(cls, payload: object) -> ReportRequest:
        """Validate the request boundary and resolve every supplied path."""
        request_payload = _request_payload(payload, CASE_REQUEST_FIELDS)

        test_case_id = _required_string(request_payload, "test_case_id")
        # Null is the honest value for a runtime throw: the harness never
        # reached an assertion, so naming one would attribute the failure to a
        # check that did not run.
        assertion_id = (
            None
            if request_payload.get("assertion_id") is None
            else _required_string(request_payload, "assertion_id")
        )
        attempt = _positive_attempt(request_payload)

        actual_vs_expected = _validate_difference(
            request_payload.get("actual_vs_expected")
        )
        generated_execution = _input_path(
            request_payload.get("generated_execution"), "generated_execution"
        )
        # The workspace those reports were produced in is wiped by the next
        # `mvn clean`, so a request that named them there would break as soon as
        # the run continued. Omitting them therefore means "read the run's own
        # archive", which is the only copy that still describes this execution.
        #
        # Nothing is inferred either way: an archive that recorded no Surefire
        # report yields no report, and a request that names neither an explicit
        # path nor an archived execution is refused rather than producing a
        # report whose runtime evidence is silently empty.
        archived = archived_execution_evidence(generated_execution)
        if "surefire_reports" not in request_payload and archived.directory is None:
            raise FailureReportError(
                "surefire_reports must be an array of paths, or the generated "
                "execution must have archived execution evidence beside it"
            )
        return cls(
            run_manifest=_input_path(
                request_payload.get("run_manifest"), "run_manifest"
            ),
            syntax_evidence=_input_path(
                request_payload.get("syntax_evidence"), "syntax_evidence"
            ),
            execution_evidence=_input_path(
                request_payload.get("execution_evidence"), "execution_evidence"
            ),
            generated_execution=generated_execution,
            reference_execution=_optional_input_path(
                request_payload.get("reference_execution"), "reference_execution"
            ),
            test_case_id=test_case_id,
            assertion_id=assertion_id,
            attempt=attempt,
            actual_target_models=_input_paths(
                request_payload.get("actual_target_models"), "actual_target_models"
            ),
            surefire_reports=(
                _input_paths(request_payload["surefire_reports"], "surefire_reports")
                if "surefire_reports" in request_payload
                else archived.surefire_reports
            ),
            execution_log=(
                _optional_input_path(
                    request_payload.get("execution_log"), "execution_log"
                )
                if "execution_log" in request_payload
                else archived.execution_log
            ),
            actual_vs_expected=actual_vs_expected,
        )


@dataclass(frozen=True)
class PairReportRequest:
    """Validated paths for one pair-level report.

    Deliberately narrower than :class:`ReportRequest`: there is no
    ``test_case_id``, no ``assertion_id``, no actual target model and no
    comparator difference, because a failure that never reached a test method
    has none of them. Every field that a per-case report would fill from the
    case is simply absent here rather than defaulted.
    """

    run_manifest: Path
    syntax_evidence: Path
    execution_evidence: Path
    generated_execution: Path
    reference_execution: Path | None
    attempt: int
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None

    @classmethod
    def from_payload(cls, payload: object) -> PairReportRequest:
        """Validate the pair-level request and resolve every supplied path."""
        request_payload = _request_payload(payload, PAIR_REQUEST_FIELDS)
        attempt = _positive_attempt(request_payload)

        generated_execution = _input_path(
            request_payload.get("generated_execution"), "generated_execution"
        )
        archived = archived_execution_evidence(generated_execution)
        return cls(
            run_manifest=_input_path(
                request_payload.get("run_manifest"), "run_manifest"
            ),
            syntax_evidence=_input_path(
                request_payload.get("syntax_evidence"), "syntax_evidence"
            ),
            execution_evidence=_input_path(
                request_payload.get("execution_evidence"), "execution_evidence"
            ),
            generated_execution=generated_execution,
            reference_execution=_optional_input_path(
                request_payload.get("reference_execution"), "reference_execution"
            ),
            attempt=attempt,
            surefire_reports=(
                _input_paths(request_payload["surefire_reports"], "surefire_reports")
                if "surefire_reports" in request_payload
                else archived.surefire_reports
            ),
            execution_log=(
                _optional_input_path(
                    request_payload.get("execution_log"), "execution_log"
                )
                if "execution_log" in request_payload
                else archived.execution_log
            ),
        )


REQUEST_TYPES: dict[str, type] = {}


def request_type(scope: str) -> type:
    """The request class for one report scope.

    The scope vocabulary is the one the diagnosis index already records, so a
    caller names the kind of report it wants rather than the class that happens
    to implement it.
    """
    try:
        return REQUEST_TYPES[scope]
    except KeyError:
        known = ", ".join(sorted(REQUEST_TYPES))
        raise FailureReportError(
            f"unknown failure-report scope {scope!r} (known: {known})"
        ) from None


def read_request_payload(path: Path) -> Any:
    """Read one repository-contained request document, without interpreting it.

    Reading and validating are separate steps because the scope decides which
    boundary the payload has to satisfy, and the caller — not this function —
    knows which kind of failure it recorded.
    """
    request_path = _input_path(path, "request")
    try:
        return read_json(request_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(
            f"cannot read failure-report request from {request_path}: {exc}"
        ) from exc


def _request_payload(
    payload: object,
    allowed_fields: frozenset[str],
) -> dict[str, Any]:
    """Validate the common JSON-object boundary for report requests."""
    if not isinstance(payload, dict):
        raise FailureReportError("request must be one JSON object")
    unknown_fields = sorted(set(payload) - allowed_fields)
    if unknown_fields:
        raise FailureReportError(
            f"request contains unknown fields: {', '.join(unknown_fields)}"
        )
    return payload


def _positive_attempt(payload: dict[str, Any]) -> int:
    """Return a validated one-based execution-attempt number."""
    attempt = payload.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise FailureReportError("attempt must be a positive integer")
    return attempt


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FailureReportError(f"{field} must be a non-empty string")
    return value


def _validate_difference(value: object) -> dict[str, list[Any]] | None:
    """Validate and normalize an optional model-level comparator difference."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FailureReportError("actual_vs_expected must be an object or null")
    problems = _difference_shape_problems(value)
    if problems:
        raise FailureReportError(f"invalid actual_vs_expected: {'; '.join(problems)}")

    normalized: dict[str, list[Any]] = {}
    for field in DIFF_FIELDS:
        entries = value[field]
        if not isinstance(entries, list):
            raise FailureReportError(f"actual_vs_expected.{field} must be an array")
        normalized[field] = entries
    return normalized


def _difference_shape_problems(value: dict[Any, Any]) -> list[str]:
    """Return missing-field and unknown-field problems in contract order."""
    missing = [field for field in DIFF_FIELDS if field not in value]
    unknown = sorted(set(value) - set(DIFF_FIELDS))
    problems: list[str] = []
    if missing:
        problems.append(f"missing fields: {', '.join(missing)}")
    if unknown:
        problems.append(f"unknown fields: {', '.join(unknown)}")
    return problems


def _input_path(value: object, label: str, *, require_file: bool = True) -> Path:
    if isinstance(value, Path):
        candidate = value
    elif isinstance(value, str) and value:
        candidate = Path(value)
    else:
        raise FailureReportError(f"{label} must be a non-empty path string")
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (REPO_ROOT / candidate).resolve()
    )
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise FailureReportError(
            f"{label} escapes the repository: {candidate}"
        ) from exc
    if require_file and not resolved.is_file():
        raise FailureReportError(f"{label} is not a file: {candidate}")
    if not require_file and not resolved.is_dir():
        raise FailureReportError(f"{label} is not a directory: {candidate}")
    return resolved


def _optional_input_path(value: object, label: str) -> Path | None:
    return None if value is None else _input_path(value, label)


def _input_paths(value: object, label: str) -> tuple[Path, ...]:
    if not isinstance(value, list):
        raise FailureReportError(f"{label} must be an array of paths")
    return tuple(
        _input_path(path, f"{label}[{index}]") for index, path in enumerate(value)
    )


def _output_path(value: Path) -> Path:
    candidate = value if value.is_absolute() else REPO_ROOT / value
    resolved = candidate.resolve()
    try:
        resolved.relative_to(TARGET.artifacts_work.resolve())
    except ValueError as exc:
        raise FailureReportError("output must stay under artifacts/work") from exc
    return resolved


REQUEST_TYPES.update({"test_case": ReportRequest, "execution_pair": PairReportRequest})
