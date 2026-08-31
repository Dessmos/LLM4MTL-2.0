"""How a stage attempt is recorded in the run store — one owner, two callers.

Two entry points drive the same stages: the local runner
(:mod:`llm4mtl.experiment_runner.orchestrator`) and the HTTP stage service
(:mod:`llm4mtl.stage_service.app`, which n8n calls). A run directory is read
without knowing which of them produced it, so both must record an attempt
identically: the same canonical stage-result payload, the same internal
evidence beside it, a ``stage_finished`` event carrying the recorded attempt
number, and the diagnosis assembler pinned to the attempt that was just
written. That policy lives here so the two cannot drift apart.

What legitimately differs between the callers stays at the call sites, because
each difference is a decision only that caller can make:

* *when a stage is announced.* The service announces before it runs the work,
  so a stage that dies mid-Maven leaves a ``stage_started`` with no
  ``stage_finished``. The runner announces as it records, because it also
  records planning errors and resumed stages that never started work.
  :func:`announce_stage_start` is therefore deliberately separate from
  :func:`record_stage_attempt` rather than folded into it.
* *which artifact references a payload carries.* The service names the
  generation records responsible for the iteration it judged, and those belong
  in the persisted result, so they are passed in as ``artifacts``. The
  diagnosis pointers it adds afterwards reach n8n through the HTTP response
  only, and stay the caller's own step on the returned payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from llm4mtl.experiment_runner.models import StageResult
from llm4mtl.run_store.events import append_event
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.stages import record_attempt
from llm4mtl.semantic_tests.diagnosis_preparation import prepare_after_execution_stage
from llm4mtl.stage_contract import to_stage_payload


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
    docstring on why the two callers announce at different moments.
    """
    append_event(paths, "stage_started", stage=stage)


def infrastructure_error_result(
    name: str,
    error: BaseException,
    *,
    input_hash: str = "",
) -> StageResult:
    """The result for stage work that raised before it could judge anything.

    Infrastructure failure is orthogonal to domain failure: the stage observed
    nothing, so it reports no domain counts and n8n routes it to retry/stop.
    """
    return StageResult(
        name,
        "infrastructure_error",
        {"infrastructure_errors": 1},
        {"error": f"{type(error).__name__}: {error}"},
        input_hash=input_hash,
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
    contract payload is what n8n reads; the runner's internal detail is kept
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
    # Only now: the report assembler pins itself to the immutable attempt that
    # was just written, so it cannot run before that evidence exists. It is
    # deterministic post-processing and changes no stage fact — the counts,
    # status, and outcome_code the attempt recorded stay exactly as validated,
    # and routing remains a decision about status and outcome_code.
    diagnosis_index = prepare_after_execution_stage(paths.root, stage, payload, attempt)
    return RecordedStageAttempt(
        payload=payload,
        attempt=attempt,
        diagnosis_index=diagnosis_index,
    )
