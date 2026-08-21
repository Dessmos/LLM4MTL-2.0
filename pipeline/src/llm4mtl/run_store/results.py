"""The terminal result of one run, written once when it ends.

The orchestration knows one thing no artifact on disk states: where the run
stopped and why — ``completed_with_failures`` because refinement was disabled,
``incomplete`` because a diagnosis set never finished. Until now that decision
lived only in the n8n execution, so reading a finished run meant reconstructing
it from the event log, from which artifacts are absent, and from the routing
rules themselves. That is acceptable while debugging one run and unacceptable as
the input to a metrics module over hundreds.

So the terminal decision is reported here, and everything else in the file is
derived from what the run itself recorded: stage statuses come from the latest
attempt of each stage, and the diagnosis aggregate from the persisted diagnosis
records. A caller can misreport where it stopped; it cannot misreport what the
stages observed.

The file is written once. A retry that reports the same terminal state reads the
first record back; a retry that reports a different one is refused, because a run
has exactly one ending.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store import stages as stage_store
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import read_json, write_json

SCHEMA_VERSION = "1.0"
RESULT_FILENAME = "result.json"
DIAGNOSIS_FILENAME = "diagnosis.json"
CONTRACT_STAGES = (
    "extract",
    "technical-validation",
    "reference-validation",
    "syntax-validation",
    "execution",
)
# Which recorded stage answers which question about the run.
SYNTAX_STAGE = "syntax-validation"
EXECUTION_STAGE = "execution"
NOT_RUN = "not_run"


class ResultConflictError(ValueError):
    """Raised when a run is asked to end a second time, differently."""


def result_path(paths: RunPaths) -> Path:
    return paths.root / RESULT_FILENAME


def read_result(paths: RunPaths) -> dict[str, Any] | None:
    path = result_path(paths)
    return read_json(path) if path.is_file() else None


def record_result(
    paths: RunPaths,
    terminal: dict[str, Any],
    diagnoses_root: Path,
) -> dict[str, Any]:
    """Assemble and persist the run's terminal result.

    ``terminal`` carries only what the orchestration owns: the status, the reason
    string it ended on, the run mode, and the refinement budget it used out of
    the one it was given.
    """
    outcome_code, _, qualifier = str(terminal["terminal_state"]).partition(":")
    classifications = _recorded_classifications(paths, Path(diagnoses_root))
    result = {
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
        "syntax_status": _stage_status(paths, SYNTAX_STAGE),
        "semantic_status": _stage_status(paths, EXECUTION_STAGE),
        "diagnosis": aggregate_classification(classifications),
        "diagnosis_records": len(classifications),
        "diagnosis_classifications": classifications,
        "stages": _stage_summary(paths),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    validate_artifact("run-result", result)

    existing = read_result(paths)
    if existing is not None:
        if _comparable(existing) != _comparable(result):
            raise ResultConflictError(
                f"run already ended as {existing['status']}:{existing['terminal_state']}"
            )
        return existing
    write_json(result_path(paths), result)
    return result


def aggregate_classification(classifications: list[str]) -> str | None:
    """The run's single verdict over every diagnosis it recorded.

    Conservative on purpose, and never a majority vote: one ambiguous verdict, or
    one of each defect kind, means the evidence points at both artefacts. This is
    the rule the orchestration routes on, applied here to the persisted records
    so the stored result cannot disagree with them.
    """
    if not classifications:
        return None
    if "AMBIGUOUS" in classifications:
        return "AMBIGUOUS"
    has_transformation = "TRANSFORMATION_DEFECT" in classifications
    has_test = "TEST_DEFECT" in classifications
    if has_transformation and has_test:
        return "AMBIGUOUS"
    return "TRANSFORMATION_DEFECT" if has_transformation else "TEST_DEFECT"


def _recorded_classifications(paths: RunPaths, diagnoses_root: Path) -> list[str]:
    """Every verdict this run persisted, in the order the attempts claimed."""
    run_diagnoses = diagnoses_root / paths.root.name
    classifications: list[str] = []
    for attempt in sorted(existing_attempts(run_diagnoses)):
        path = run_diagnoses / f"attempt-{attempt:03d}" / DIAGNOSIS_FILENAME
        if path.is_file():
            classifications.append(str(read_json(path)["classification"]))
    return classifications


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


def _comparable(result: dict[str, Any]) -> dict[str, Any]:
    """The result without the wall-clock stamp, which a retry legitimately moves."""
    return {key: value for key, value in result.items() if key != "recorded_at"}
