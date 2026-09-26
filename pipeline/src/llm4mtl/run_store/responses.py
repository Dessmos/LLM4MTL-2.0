"""Immutable storage of the failure diagnoses of a run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.attempts import (
    attempt_dir_name,
    claim_attempt,
    existing_attempts,
)
from llm4mtl.serialization.json_io import write_json

DIAGNOSIS_FILENAME = "diagnosis.json"


def diagnosis_record(run_diagnoses: Path, attempt: int) -> Path:
    """Where diagnosis attempt ``attempt`` of one run is stored."""
    return Path(run_diagnoses) / attempt_dir_name(attempt) / DIAGNOSIS_FILENAME


def recorded_diagnoses(run_diagnoses: Path) -> list[Path]:
    """Every stored diagnosis of one run, in the order the attempts were claimed."""
    records = (
        diagnosis_record(run_diagnoses, attempt)
        for attempt in sorted(existing_attempts(Path(run_diagnoses)))
    )
    return [record for record in records if record.is_file()]


def record_diagnosis(
    diagnosis: dict[str, Any], run_diagnoses: Path
) -> tuple[int, Path]:
    """Persist one immutable failure diagnosis outside the run that produced it.

    Downstream work consumes the verdict, so it is stored under
    ``run_diagnoses``: the run's own directory in the diagnoses area, which the
    caller resolves through the artifact layout. Each diagnosis claims the next
    free attempt directory, so a second diagnosis never overwrites the first.

    Returns the attempt and the written file.
    """
    validate_artifact("diagnosis", diagnosis)
    run_diagnoses = Path(run_diagnoses)
    attempt = claim_attempt(
        run_diagnoses,
        lambda number: run_diagnoses / attempt_dir_name(number),
    )
    target = diagnosis_record(run_diagnoses, attempt)
    write_json(target, diagnosis)
    return attempt, target
