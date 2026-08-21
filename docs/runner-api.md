# Stage service API

> Status: implemented. Code:
> `pipeline/src/llm4mtl/stage_service/`.

The FastAPI service is a transport adapter for n8n. Business logic remains in
the shared Python stages and language adapters. The service requires Python,
JDK, Maven, repository inputs, and the frozen engine templates at runtime.

## Endpoints

```http
GET  /health
POST /prompt-inputs/resolve
POST /runs
GET  /runs/{run_id}

POST /runs/{run_id}/stages/{stage}
GET  /runs/{run_id}/stages/{stage}

POST /runs/{run_id}/refinements
POST /runs/{run_id}/generations
GET  /runs/{run_id}/diagnosis/execution/{attempt}
POST /runs/{run_id}/diagnoses
POST /runs/{run_id}/result
```

## Resolve exact prompt inputs

```http
POST /prompt-inputs/resolve
Content-Type: application/json
```

```json
{"language": "etl", "task": "Tree2Graph"}
```

The service loads `benchmark/tasks/<language>/task_contracts/<task>.json`,
validates it, follows its exact repository-relative reference and
`metamodelFile` paths, and reads the language grammar. Paths must remain inside
the corresponding protected `benchmark` trees. There is no filename search or
language-wide metamodel fallback.

The response contains `reference`, `metamodels`, `metamodel_text`, and `grammar`
with their repository-relative paths and UTF-8 content. It includes
`contract_path` for provenance, but never the raw task-contract JSON supplied
to the resolver. n8n passes the resolved reference, metamodel contents, grammar,
and task name to the prompt-generation LLM.

Unknown tasks, invalid contracts, stale paths, and path traversal return `422`.

## Health

```http
GET /health
```

```json
{"status": "ok"}
```

## Create a run

```http
POST /runs
Content-Type: application/json
```

Every identity axis is explicit:

```json
{
  "run_id": "etl-tree2graph-seed1",
  "language": "etl",
  "task": "Tree2Graph",
  "transformation_model": "gpt-5",
  "test_generation_model": "gpt-5",
  "transformation_strategy": "grammar",
  "test_generation_strategy": "few_shot",
  "seed": 1,
  "pipeline_variant": "full",
  "preset": "tree2graph_smoke"
}
```

`run_id` and `preset` are optional. A generated or supplied run id must match:

```text
[A-Za-z0-9._-]+
```

The service writes an immutable schema-validated manifest and a `run_created`
event. Run creation also resolves mandatory provenance: git revision/dirty
state, schema and renderer versions, runtime tool versions, and protected-input
hashes.

Response:

```json
{
  "run_id": "etl-tree2graph-seed1",
  "status": "initialized"
}
```

Important errors:

- `400` — malformed or escaping run id;
- `409` — the immutable manifest already exists;
- `422` — missing/unknown identity field, `task="all"`, unsupported adapter, or
  missing mandatory provenance input.

## Run a stage

```http
POST /runs/{run_id}/stages/{stage}
Content-Type: application/json
```

Implemented stage ids:

```text
extract
syntax-validation
technical-validation
reference-validation
execution
```

The body contains only attempt-specific controls:

```json
{
  "suite_id": "suite_001",
  "refinement_iteration": 0,
  "verbose": false
}
```

An empty object is valid. `suite_id`, when present, uses the same opaque
one-component identifier syntax. Identity fields and all other unknown fields
are rejected with `422`; the service reconstructs language/task/model/strategy
selection exclusively from `manifest.json`.

`refinement_iteration` is the artifact-specific iteration consumed by the
stage. Test and transformation iterations may differ; the master sends the test
iteration to extraction and the transformation iteration to syntax/execution.

Executable stages atomically materialize the language harness under the current
run. They never execute in the shared `engines/**` template.

Response and persisted `result.json`:

```json
{
  "schema_version": "2.0",
  "stage": "syntax-validation",
  "status": "passed",
  "outcome_code": "SYNTAX_VALID",
  "counts": {
    "selected": 1,
    "passed": 1,
    "failed": 0
  },
  "artifacts": {},
  "attempt": 1
}
```

An adapter exception is normalized into:

```text
status = infrastructure_error
outcome_code = INFRASTRUCTURE_ERROR
```

It is still recorded as an immutable attempt so the failed invocation remains
auditable.

## Read a stage result

```http
GET /runs/{run_id}/stages/{stage}
```

Returns the highest-numbered recorded `result.json`. There is no mutable
`latest.json`.

`404` means the stage has no recorded result.

For `execution`, a recovered result also re-derives `failure_report_index` and
the first eligible `failure_report_path` from the schema-validated diagnosis
index. They are routing references, not mutable stage facts.

## Prepare and record generation

Before refinement, n8n calls `POST /runs/{run_id}/refinements` with the artifact
type, consecutive iterations, configured refinement provider/model, and the
recorded failure reason. Semantic refinement also names the exact
`execution_attempt` that produced the decision. Python resolves the previous
artifact and only the parser, execution, failure-report, and diagnosis facts
belonging to that evidence set. It writes a schema-validated `request.json` and exact `prompt.md` below
`refinements/<artifact-type>/iteration-NNN/`. n8n passes that prompt unchanged
to its selected LLM.

After every initial generation or refinement, n8n calls
`POST /runs/{run_id}/generations` before validation continues. The body reports
the actual provider/model selected inside n8n. Python verifies the raw output
exists and writes `generations/<artifact-type>/iteration-NNN/generation.json`
with hashes of the persisted prompt input, prior artifact, raw output, and
refinement request. Semantic-test workflows archive their fully assembled
prompt; initial transformation generation currently hashes the frozen task
prompt because the legacy export does not archive its assembled request.

`GET /runs/{run_id}/diagnosis/execution/{attempt}` validates the stored index and
every eligible failure-report reference: containment, existence, report schema,
run id, and execution attempt. Only then does it return the queue. The master
uses this endpoint instead of parsing diagnosis files itself, including after
resume.

## Read a run

```http
GET /runs/{run_id}
```

```json
{
  "run_id": "etl-tree2graph-seed1",
  "manifest": {
    "schema_version": "2.0",
    "run_id": "etl-tree2graph-seed1",
    "language": "etl",
    "task": "Tree2Graph"
  },
  "stages": [
    "extract",
    "syntax-validation"
  ]
}
```

The example abbreviates the manifest; the stored document also contains every
identity axis, provenance, and `started_at`.

## Record an n8n diagnosis

```http
POST /runs/{run_id}/diagnoses
Content-Type: application/json
```

```json
{
  "schema_version": "1.0",
  "classification": "AMBIGUOUS",
  "evidence_ref": "stages/execution/attempts/attempt-001/result.json",
  "rationale": "The available evidence does not distinguish the failure source.",
  "provider": "openai",
  "model": "gpt-5",
  "created_at": "2026-07-29T12:00:00Z"
}
```

The service validates the payload and records the verdict outside the run, in
the area consumers read:

```text
artifacts/work/diagnoses/<run-id>/attempt-NNN/diagnosis.json
```

The returned `artifact` is that path relative to `artifacts/work/diagnoses/`.
The service then appends `diagnosis_recorded` to the run's own journal. Unknown fields and invalid classifications
return `422`.

## Persistence and concurrency

```text
artifacts/work/runs/<run-id>/
├── manifest.json
├── events.jsonl
├── observations/
├── workspaces/
├── responses/
├── refinements/<artifact-type>/iteration-NNN/{request.json,prompt.md}
├── generations/<artifact-type>/iteration-NNN/generation.json
└── stages/<stage>/attempts/attempt-NNN/
    ├── result.json
    └── evidence.json
```

- Manifest creation is atomic and write-once.
- Event appends are locked and fsynced.
- Attempt directories are claimed with atomic `mkdir`.
- Canonical payloads are validated against their schemas before persistence.
- Internal evidence is written before `result.json`, which makes the attempt
  visible as recorded.
- Technical/reference observation creation is locked per suite and input hash.
