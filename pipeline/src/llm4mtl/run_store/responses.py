"""Immutable normalized LLM-response storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.attempts import claim_attempt
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import write_json

DIAGNOSIS_FILENAME = "diagnosis.json"


def record_diagnosis(
    paths: RunPaths, diagnosis: dict[str, Any], run_diagnoses: Path
) -> tuple[int, Path]:
    """Persist one immutable failure diagnosis outside the run that produced it.

    The verdict is what downstream work consumes, so it is stored under
    ``run_diagnoses`` — the run's own directory in the diagnoses area, which the
    caller resolves through the artifact layout — rather than among the run's
    state. Numbering is unchanged: each diagnosis of a run claims the next free
    attempt directory, so a second diagnosis can never overwrite the first.

    Returns the attempt and the written file.
    """
    validate_artifact("diagnosis", diagnosis)
    run_diagnoses = Path(run_diagnoses)
    attempt = claim_attempt(
        run_diagnoses,
        lambda number: run_diagnoses / f"attempt-{number:03d}",
    )
    target = run_diagnoses / f"attempt-{attempt:03d}" / DIAGNOSIS_FILENAME
    write_json(target, diagnosis)
    return attempt, target
