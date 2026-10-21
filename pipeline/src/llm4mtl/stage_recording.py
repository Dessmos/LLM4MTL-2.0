"""How a stage attempt is recorded in the run store.

Recording an attempt means writing the canonical stage-result payload, the
internal evidence beside it, a ``stage_finished`` event with the attempt
number, and preparing diagnosis evidence for the attempt just written.

The stage service (:mod:`llm4mtl.stage_service.app`) calls these functions in
two steps:

* *It announces the stage before the work.* So a stage that dies mid-Maven
  leaves a ``stage_started`` event with no ``stage_finished``. That is why
  :func:`announce_stage_start` is separate from :func:`record_stage_attempt`.
* *It passes the generation records of the iteration it judged as
  ``artifacts``,* so they are persisted. The diagnosis pointers it adds
  afterwards reach n8n only through the HTTP response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from llm4mtl.run_store.events import append_event
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.stages import record_attempt
from llm4mtl.semantic_tests.diagnosis_preparation import prepare_after_execution_stage
from llm4mtl.stage_contract import to_stage_payload
from llm4mtl.stages.models import StageResult


@dataclass(frozen=True)
class RecordedStageAttempt:
    """One immutable attempt, as it was written.

    ``payload`` is the canonical stage-result payload that was persisted,
    including its ``attempt`` number, so a caller that returns it to n8n and a
    reader of ``result.json`` see the same facts.
    """

    payload: dict[str, Any]
    attempt: int
    diagnosis_index: dict[str, Any] | None


def announce_stage_start(paths: RunPaths, stage: str) -> None:
    """Record that ``stage`` began.

    Separate from :func:`record_stage_attempt` on purpose: see the module
    docstring.
    """
    append_event(paths, "stage_started", stage=stage)


def infrastructure_error_result(name: str, error: BaseException) -> StageResult:
    """The result for stage work that raised before it could judge anything.

    Infrastructure failure is orthogonal to domain failure: the stage observed
    nothing, so it reports no domain counts and n8n routes it to retry/stop.
    """
    return StageResult(
        name,
        "infrastructure_error",
        {"infrastructure_errors": 1},
        {"error": f"{type(error).__name__}: {error}"},
        exit_code=1,
    )


def record_stage_attempt(
    paths: RunPaths,
    stage: str,
    result: StageResult,
    *,
    artifacts: Mapping[str, str] | None = None,
) -> RecordedStageAttempt:
    """Persist one immutable attempt and everything that must accompany it.

    ``stage`` is the contract stage id, never an internal pipeline name. The
    contract payload is what n8n reads; the stage's internal detail is kept
    beside it as evidence, which is explicitly not a contract.
    """
    payload = to_stage_payload(stage, result)
    payload["artifacts"] = {**payload.get("artifacts", {}), **(artifacts or {})}
    attempt = record_attempt(paths, stage, payload, evidence=result.to_dict())
    payload["attempt"] = attempt
    append_event(
        paths,
        "stage_finished",
        stage=stage,
        status=payload["status"],
        outcome_code=payload["outcome_code"],
        attempt=attempt,
    )
    # Only after the write: diagnosis preparation reads the attempt just
    # recorded. It is deterministic post-processing and changes no stage fact;
    # the recorded counts, status and outcome_code stay as validated.
    diagnosis_index = prepare_after_execution_stage(paths.root, stage, payload, attempt)
    return RecordedStageAttempt(
        payload=payload,
        attempt=attempt,
        diagnosis_index=diagnosis_index,
    )
