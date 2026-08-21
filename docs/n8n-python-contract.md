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

The model values on this Python boundary are stable artifact-family ids, such
as `gpt-5`, `claude-sonnet-4`, and `gemini-2-5-pro`. Provider-specific exact
ids remain inside n8n and are passed to the selected AI Model nodes; Python uses
the family ids for generated-suite identity and selection. Raw master-workflow
responses are selected by run, artifact iteration, and task instead.

One run represents one concrete task. A matrix must expand multi-task or
multi-model experiments before calling the service.

Stage requests cannot repeat or override identity fields. Their accepted body is
limited to:

```json
{
  "suite_id": "suite_001",
  "refinement_iteration": 0,
  "verbose": false
}
```

`refinement_iteration` says which iteration of the artifact consumed by that
stage the attempt belongs to. The master keeps test and transformation artifact
iterations separately from the shared refinement-budget count. It is not
derivable from `suite_id`: a refined *suite* gets a new id, while a refined
*transformation* is judged against the suite that already passed on the
reference and therefore keeps the old one.

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

## Prepared diagnosis evidence

A failing `execution` attempt prepares its own diagnosis evidence before the
call returns. The stage result is unchanged — routing is still a decision about
`status`/`outcome_code` — and the evidence is fetched by its own path:

```text
<run>/diagnosis/execution/attempt-NNN/
    index.json                  every failing pair, its reports, and why a pair has none
    reports/<sha12>__<suite>__<case>__<assertion>.json   per-case report
    reports/<sha12>__<suite>__execution-pair.json        pair-level report
```

Two report types, chosen by what the run could attribute the failure to:

| `report_type` | when | subject |
| --- | --- | --- |
| `semantic_test_case_failure` | Surefire named a failing test method | one case, and for an assertion failure one assertion |
| `semantic_execution_pair_failure` | it named none | one suite against one transformation |

The pair-level report exists for failures that happened before any test method
was reported — the engine refused the transformation, the harness died during
setup — which are real failures of a reference-validated suite and are not
dropped for lacking a case. It names none: `test_case_id`, `assertion_id`,
`expected`, and `actual` are all `null`, the whole generated test is supplied
instead of a selected case, and its body lives under `pair_result` rather than
`test_case_result`. The two are mutually exclusive per pair, so one failure is
never counted twice.

Its eligibility adds two conditions to the per-case ones: the execution must
have been attempted, and no narrower attribution may exist —
`execution_not_attempted` and `per_test_failure_available` are the reasons that
say otherwise. Its eligible reason is
`parser_passed_and_execution_failed_before_any_test`.

`index.json` carries `counts.reports_created`, `counts.pair_level_reports`,
`counts.diagnosis_eligible`, and per report a `scope` and a `reason`. These
count prepared evidence, never experiment results: the stage's own counts were
written before preparation ran and preparation never touches them, so a report
coming into existence cannot move a semantic result. n8n calls the diagnosis LLM only for a report with
`source_diagnosis.eligible = true`, and passes
`source_diagnosis.evidence_bundle` — the task description, the exact metamodels,
the generated transformation, the one failing case and assertion, and the
execution output, each fact once. The bundle is deliberately smaller than the
stored report: no hashes, no nested stage-evidence document, and the Maven log
reduced to the lines Maven itself marked (`[ERROR]`, `[WARNING]`, the Surefire
summary, the build verdict). The stored report keeps the wider tail excerpt and
the complete stream stays in `execution_evidence/maven-stdout.log`.

A report with `eligible = false` states why in `source_diagnosis.reason`:

```text
transformation_parser_check_failed        the transformation never passed the parser
semantic_test_passed                      not a failure
failure_not_attributable_to_the_pairing   a timeout or an infrastructure failure
reference_result_not_passing              the suite did not pass on the reference
no_recorded_input_model                   the case names no readable source model
no_observed_failure_evidence              nothing was observed about the failure
```

A runtime throw is **not** among them. A validated test that throws on a
generated transformation has failed against it, and attributing that failure is
exactly what Source Diagnosis is for. Such a report names no assertion
(`assertion_id: null`), carries the exception and its stack trace as evidence,
and leaves `expected`/`actual` null rather than reconstructing them.

The same assembly is reproducible outside the stage call with
`llm4mtl diagnosis prepare --run <run-id> [--attempt N]`; the index is written
once per attempt and re-reading it returns the same document.

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

## Transformation inputs a run keeps

The master narrows each transient generation workflow to the selected task and
writes both kinds of raw response below the current run:

```text
runs/<run-id>/responses/semantic-test-generation/iteration-<NNN>/<Task>.md
runs/<run-id>/responses/transformation-generation/iteration-<NNN>/<Task>.<ext>
```

The first stage that judges a transformation — `syntax-validation`, or
`execution` when the parser is ablated — adopts that run-scoped response before
judging it:

```text
runs/<run-id>/transformation/iteration-<NNN>/<Task>.<ext>
runs/<run-id>/transformation/iteration-<NNN>/metadata.json
```

Every later stage of that iteration is handed the copy, so the parser and the
executor cannot end up judging different bytes, and a recorded result stays
backed by the input that produced it. `<NNN>` is the transformation artifact
iteration stated in the stage request. A test refinement leaves it unchanged; a
transformation refinement increments it without renaming the validated suite.

`metadata.json` (`schemas/transformation-adoption.schema.json`) records the
manifest's transformation-model family, the strategy, the sha256 of each copy
and the run-scoped path it came from. The current generation workflows do not
persist the exact provider/model used by a refinement; that provenance gap is
not filled by guessing it in Python.

The stage service adopts on the call n8n already makes.

## Terminal run result

The terminal decision is n8n's, so n8n reports it once, when the state machine
reaches `final`:

```text
POST /runs/<run-id>/result
```

```json
{
  "status": "completed_with_failures",
  "terminal_state": "DIAGNOSED_TRANSFORMATION_DEFECT:REFINEMENT_LIMIT_REACHED",
  "run_mode": "full",
  "refinement_iterations_used": 0,
  "refinement_iterations_allowed": 0,
  "suite_id": "etl-tree2graph-20260820_000"
}
```

Nothing else is representable. Python splits `terminal_state` into the
`outcome_code` and the qualifier that stopped the run there, and derives every
other field from what the run itself recorded — stage statuses from the latest
attempt of each stage, the diagnosis aggregate from the persisted diagnosis
records. A stale workflow therefore cannot report a run as passing that its own
stages recorded as failing. The result is written once to
`runs/<run-id>/result.json` (`schemas/run-result.schema.json`); re-posting the
same ending returns the stored one, a different ending is a `409`.

`diagnosis_records` counts the verdicts, not the defects: one broken
transformation fails every test case that uses it, and each failing case gets its
own report and its own verdict. Clustering those observations into distinct
failures is evaluation's job — `llm4mtl diagnosis aggregate --run <run-id>` —
and never the pipeline's.

## Retry and concurrency rules

- Every stage/diagnosis invocation gets an immutable atomic attempt number.
- A retry adds an attempt; it does not replace history.
- The latest result is derived from the highest recorded attempt.
- Run events are append-only.
- Technical and reference calls for the same suite share a locked run-local
  execution observation rather than racing the harness or executing twice.
