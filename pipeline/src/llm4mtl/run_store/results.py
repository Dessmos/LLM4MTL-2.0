"""The terminal result of one run, written once when it ends.

The orchestration knows one thing no other artifact states: where the run
stopped and why, for example ``completed_with_failures`` because refinement was
disabled, or ``incomplete`` because a diagnosis set never finished. Without this
file, metrics would have to rebuild that decision from the event log and the
n8n routing rules.

Only the terminal decision comes from the caller. Everything else is derived
from what the run recorded: stage statuses from the latest attempt of each
stage, and the diagnosis aggregate from the stored diagnosis records. A caller
can misreport where it stopped; it cannot misreport what the stages observed.

The file is written once. A retry that reports the same terminal state reads the
first record back; a retry that reports a different one is refused, because a run
has exactly one ending.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.domain.diagnosis import aggregate_classifications
from llm4mtl.run_store import stages as stage_store
from llm4mtl.run_store.models import RECORDED_AT, RunPaths, without_recorded_at
from llm4mtl.run_store.responses import recorded_diagnoses
from llm4mtl.serialization.json_io import (
    JsonDocumentConflictError,
    read_json,
    write_json_once_or_match,
)
from llm4mtl.vocabulary import (
    EXECUTION_STAGE_ID,
    EXTRACT_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_ID,
    SYNTAX_VALIDATION_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_ID,
)

SCHEMA_VERSION = "1.0"
RESULT_FILENAME = "result.json"
CONTRACT_STAGES = (
    EXTRACT_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_ID,
    SYNTAX_VALIDATION_STAGE_ID,
    EXECUTION_STAGE_ID,
)
NOT_RUN = "not_run"


class ResultConflictError(ValueError):
    """Raised when a run is asked to end a second time, differently."""


def result_path(paths: RunPaths) -> Path:
    return paths.root / RESULT_FILENAME


def record_result(
    paths: RunPaths,
    terminal: dict[str, Any],
    run_diagnoses: Path,
) -> dict[str, Any]:
    """Assemble and persist the run's terminal result.

    ``terminal`` carries only what the orchestration owns: the status, the reason
    string it ended on, the run mode, and the refinement budget it used out of
    the one it was given. ``run_diagnoses`` is where this run's verdicts were
    recorded, resolved by the caller through the artifact layout.

    The result is written once, also when two calls race. Reporting the same
    ending again returns the stored result; a different ending raises
    :class:`ResultConflictError`.
    """
    result = _assemble_result(paths, terminal, Path(run_diagnoses))
    validate_artifact("run-result", result)
    try:
        return write_json_once_or_match(
            result_path(paths), result, comparable=without_recorded_at
        )
    except JsonDocumentConflictError as exc:
        stored = exc.stored
        raise ResultConflictError(
            f"run already ended as {stored['status']}:{stored['terminal_state']}"
        ) from exc


def _assemble_result(
    paths: RunPaths, terminal: dict[str, Any], run_diagnoses: Path
) -> dict[str, Any]:
    """The terminal facts the caller reported, plus what the run recorded."""
    outcome_code, _, qualifier = str(terminal["terminal_state"]).partition(":")
    classifications = _recorded_classifications(run_diagnoses)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": paths.root.name,
        "status": terminal["status"],
        "outcome_code": outcome_code,
        "terminal_reason": qualifier or None,
        "terminal_state": terminal["terminal_state"],
        "run_mode": terminal["run_mode"],
        "refinement_iterations_used": terminal["refinement_iterations_used"],
        "refinement_iterations_allowed": terminal["refinement_iterations_allowed"],
        "suite_id": terminal.get("suite_id"),
        "failed_component": terminal.get("failed_component"),
        "last_completed_stage": terminal.get("last_completed_stage"),
        "test_iteration": terminal.get("test_iteration"),
        "transformation_iteration": terminal.get("transformation_iteration"),
        "syntax_status": _stage_status(paths, SYNTAX_VALIDATION_STAGE_ID),
        "semantic_status": _stage_status(paths, EXECUTION_STAGE_ID),
        "diagnosis": aggregate_classifications(classifications),
        "diagnosis_records": len(classifications),
        "diagnosis_classifications": classifications,
        "stages": _stage_summary(paths),
        RECORDED_AT: datetime.now(timezone.utc).isoformat(),
    }


def _recorded_classifications(run_diagnoses: Path) -> list[str]:
    """Every verdict this run persisted, in the order the attempts claimed."""
    return [
        str(read_json(record)["classification"])
        for record in recorded_diagnoses(run_diagnoses)
    ]


def _stage_status(paths: RunPaths, stage: str) -> str:
    latest = stage_store.read_latest(paths, stage)
    return str(latest["status"]) if latest else NOT_RUN


def _stage_summary(paths: RunPaths) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for stage in CONTRACT_STAGES:
        latest = stage_store.read_latest(paths, stage)
        if latest is None:
            continue
        summary[stage] = {
            "status": latest["status"],
            "outcome_code": latest.get("outcome_code"),
            "attempt": latest.get("attempt"),
        }
    return summary
