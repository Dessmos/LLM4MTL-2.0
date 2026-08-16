# n8n ↔ Python contract

> Status: implemented boundary for the current stages. Transition policy remains
> n8n-owned and may evolve without changing Python facts.

## Ownership rule

n8n invokes Python through the stage service and reads the canonical result
defined by `schemas/stage-result.schema.json`.

Python reports:

```text
status
outcome_code
counts
artifact references
```

Python never reports `next_action`. n8n owns routing, provider/model selection,
LLM retries, iteration limits, and stop conditions.

## Run identity

`POST /runs` fixes one immutable combination:

```text
language
task
transformation_model
test_generation_model
transformation_strategy
test_generation_strategy
seed
pipeline_variant
```

One run represents one concrete task. A matrix must expand multi-task or
multi-model experiments before calling the service.

Stage requests cannot repeat or override identity fields. Their accepted body is
limited to:

```json
{
  "suite_id": "suite_001",
  "verbose": false
}
```

Unknown fields fail with `422`, including identity fields that happen to equal
the manifest.

## Canonical stage result

The persisted and returned contract is version `2.0`:

```json
{
  "schema_version": "2.0",
  "stage": "reference-validation",
  "status": "failed",
  "outcome_code": "REFERENCE_VALIDATION_FAILED",
  "counts": {
    "selected": 1,
    "validated": 0,
    "invalid": 1,
    "skipped": 0
  },
  "artifacts": {},
  "attempt": 1
}
```

`result.json` contains only this contract. Commands, selected inputs, raw error
detail, and internal hashes belong in the adjacent `evidence.json`.

### Status vocabulary

- `passed` — the stage observed no domain or infrastructure failure;
- `failed` — the stage observed a domain failure;
- `skipped` — the stage produced no applicable observation;
- `infrastructure_error` — the experiment could not establish a domain fact.

`skipped` is never translated to `passed`. Partial per-item skips remain visible
in counts; a completely skipped stage makes local run status `incomplete`.

## Implemented stages and outcome codes

| stage | outcome codes | factual meaning |
| --- | --- | --- |
| `extract` | `EXTRACTED`, `TEST_SPEC_INVALID`, `INFRASTRUCTURE_ERROR` | structured suite created or the generated test specification was unusable |
| `syntax-validation` | `SYNTAX_VALID`, `SYNTAX_INVALID`, `INFRASTRUCTURE_ERROR` | selected generated transformations were or were not accepted by the parser |
| `technical-validation` | `TECH_VALID`, `TECH_COMPILE_FAILED`, `TECH_EXEC_FAILED`, `TEST_SPEC_INVALID`, `INFRASTRUCTURE_ERROR` | artifact validity and technical execution facts |
| `reference-validation` | `REFERENCE_VALIDATED`, `REFERENCE_VALIDATION_FAILED`, `SKIPPED_NOT_EXECUTABLE`, `INFRASTRUCTURE_ERROR` | technically executable suite did or did not pass on the reference |
| `execution` | `SEMANTIC_PASSED`, `SEMANTIC_EXECUTION_FAILED`, `SKIPPED_NO_PARSED_TRANSFORMATIONS`, `INFRASTRUCTURE_ERROR` | reference-valid suite did or did not pass on generated transformation |

The generic skip fallback is `SKIPPED`; stage implementations should provide a
specific recorded reason where policy needs to distinguish missing upstream
evidence.

### Unrecognized runtime failures

`unclassified_runtime` is an execution-PHASE observation: the run threw and no
marker identified which phase threw. It is never a statement about who is at
fault. The two stages read it differently, and both readings follow from where
the suite is in the pipeline:

* **reference validation** — the suite has not been proven yet, so an
  unclassified throw (like `model_loading` or `engine_runtime`) leaves it
  `NOT_EXECUTABLE`. It is not reference-validated and never reaches the
  generated-transformation stage.
* **execution against a generated transformation** — every pair here has a
  reference-validated suite, so the same phase counts as a semantic execution
  failure (`failed`).

Attribution — transformation, test, or neither — is decided only by Source
Diagnosis, from the evidence the observation carries.

## Execution evidence

Maven writes its Surefire XML into the engine workspace, and every execution
starts with `mvn clean`. The reports explaining execution N therefore stop
existing when execution N+1 begins, and the workspace is scratch space that no
recorded result may depend on.

Each execution observation is therefore archived together with the evidence it
was derived from, at the moment the observation is written:

```text
<run>/observations/.../<suite_id>/
    suite_execution.json                     the observation and its verdict
    execution_evidence/
        evidence.json                        schemas/execution-evidence.schema.json
        maven-stdout.log                     complete, untruncated
        maven-stderr.log                     complete, untruncated
        surefire/TEST-*.xml                  every report that existed
```

For generated-transformation executions the observation root already carries the
transformation hash, so the archive is per execution pair. `evidence.json` names
the suite, the transformation, and its role (`reference_transformation` or
`generated_transformation`), so evidence can never be read against the wrong
execution.

`surefire.present` is recorded explicitly, and the counts are `null` when no
report parsed. An absent report is never presented as a run with no failures.

`error_summary` on the observation remains a short derived summary for routing;
it is not a substitute for the archived streams. Source Diagnosis reads the
archive — a failure-report request that omits `surefire_reports` resolves them
from it.

## Validation-funnel routing facts

One physical reference execution yields both technical and oracle facts:

```text
assertions_evaluated = true
assertions_passed = false
  → technical-validation: TECH_VALID
  → reference-validation: REFERENCE_VALIDATION_FAILED
```

n8n must not route that case as a compile/technical repair. Conversely, a
compile failure or a runtime failure before assertions were evaluated is not
evidence that the oracle is wrong.

## Suggested transition policy

The table below is policy guidance, not Python-owned state:

| outcome | typical n8n action |
| --- | --- |
| `TEST_SPEC_INVALID` | regenerate or refine the semantic-test specification |
| `SYNTAX_INVALID` | repair the generated transformation |
| `TECH_COMPILE_FAILED` / `TECH_EXEC_FAILED` | repair or regenerate the test artifact |
| `REFERENCE_VALIDATION_FAILED` | treat as an invalid oracle and refine the test |
| `SEMANTIC_EXECUTION_FAILED` | prepare evidence and diagnose the failure source |
| `INFRASTRUCTURE_ERROR` | bounded retry or stop; never ask an LLM to “repair” infrastructure |
| `SKIPPED_*` | resolve missing prerequisite or terminate as incomplete |

## Diagnosis result

The diagnosis LLM runs in n8n and returns exactly:

```json
{
  "classification": "transformation_defect",
  "confidence": "high",
  "reasoning_summary": "The generated transformation omitted the target node.",
  "evidence": ["The expected node is listed in missing_elements."],
  "test_case_id": "case-1"
}
```

`classification` is `transformation_defect`, `test_defect`, or `ambiguous`.
n8n does not route inside the diagnosis subworkflow. It maps the verdict to the
existing Python persistence contract before calling the stage service:

```json
{
  "schema_version": "1.0",
  "classification": "TRANSFORMATION_DEFECT",
  "evidence_ref": "stages/execution/attempts/attempt-001/result.json",
  "rationale": "The generated transformation omitted the target node.",
  "provider": "openai",
  "model": "gpt-5",
  "created_at": "2026-07-29T12:00:00Z"
}
```

The persisted `classification` is one of:

```text
TRANSFORMATION_DEFECT
TEST_DEFECT
AMBIGUOUS
```

Python validates and stores this fact, but does not choose the resulting branch.

## Retry and concurrency rules

- Every stage/diagnosis invocation gets an immutable atomic attempt number.
- A retry adds an attempt; it does not replace history.
- The latest result is derived from the highest recorded attempt.
- Run events are append-only.
- Technical and reference calls for the same suite share a locked run-local
  execution observation rather than racing the harness or executing twice.
