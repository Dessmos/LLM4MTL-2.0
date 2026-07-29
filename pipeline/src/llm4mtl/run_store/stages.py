"""Per-stage result store: immutable attempts, and a latest derived from them.

``result`` is the canonical stage-result payload (``schemas/stage-result.schema.json``)
and is validated before it is written. Anything a stage knows beyond that contract
— commands, stdout, selected inputs — belongs in ``evidence``, which is stored
beside the result and is explicitly not a contract for n8n.

There is deliberately no mutable ``latest.json``. A projection written after each
attempt is a second copy of state that two concurrent stage calls can leave
pointing at the older attempt — and n8n routes on exactly that value. Deriving
the latest attempt from the immutable attempts on disk makes a stale answer
impossible rather than merely unlikely.
"""

from __future__ import annotations

from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.run_store.attempts import claim_attempt, existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import read_json, write_json


def record_attempt(
    paths: RunPaths,
    stage: str,
    result: dict[str, Any],
    *,
    evidence: dict[str, Any] | None = None,
) -> int:
    """Persist an immutable attempt; returns the attempt number."""
    payload = {**result, "stage": stage}
    # Validate the caller-controlled contract before claiming a number. An
    # invalid payload must not leave an empty attempt that looks like a crashed
    # scientific observation and shifts all later attempt identities.
    validate_artifact("stage-result", payload)
    attempt = claim_attempt(
        paths.stage_attempts_dir(stage),
        lambda number: paths.stage_attempt_dir(stage, number),
    )
    payload["attempt"] = attempt
    validate_artifact("stage-result", payload)

    if evidence is not None:
        write_json(paths.stage_attempt_evidence(stage, attempt), evidence)
    # Written last: the result file is what makes an attempt count as recorded,
    # so its evidence is already in place when a reader can first see it.
    write_json(paths.stage_attempt_result(stage, attempt), payload)
    return attempt


def read_latest(paths: RunPaths, stage: str) -> dict[str, Any] | None:
    """The highest-numbered recorded attempt for ``stage``.

    Derived on read, so it can never regress to an earlier attempt.
    """
    for attempt in sorted(existing_attempts(paths.stage_attempts_dir(stage)), reverse=True):
        result = paths.stage_attempt_result(stage, attempt)
        if result.is_file():
            payload = read_json(result)
            validate_artifact("stage-result", payload)
            return payload
    return None


def list_stages(paths: RunPaths) -> list[str]:
    if not paths.stages_dir.is_dir():
        return []
    return sorted(item.name for item in paths.stages_dir.iterdir() if item.is_dir())
