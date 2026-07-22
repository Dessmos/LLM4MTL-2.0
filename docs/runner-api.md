# Stage service API

> Status: **implemented (Stage 5)**. Code: `pipeline/src/llm4mtl/stage_service/`.
> Deployment: `pipeline/stage_service/` (Dockerfile + compose).

A thin FastAPI service (transport only, no business logic) that lets n8n drive the
pipeline. It runs in a container with Python + JDK + Maven + the engines. Python
reports facts; routing lives in n8n (see `n8n-python-contract.md`).

```http
GET  /health                              → 200 {"status": "ok"}
POST /runs                                → 200 {"run_id", "status": "initialized"}
POST /runs/{run_id}/stages/{stage}        → 200 <stage-result payload>
GET  /runs/{run_id}/stages/{stage}        → 200 <latest stage result>
GET  /runs/{run_id}                       → 200 {"run_id", "manifest", "stages": [...]}
```

`{stage}` ∈ `extract | syntax-validation | technical-validation |
reference-validation | execution`. The stage-result payload matches
`schemas/stage-result.schema.json` plus `counts`:

```json
{
  "schema_version": "1.0",
  "stage": "syntax-validation",
  "status": "passed",
  "outcome_code": "SYNTAX_VALID",
  "counts": {"selected": 1, "passed": 1, "failed": 0},
  "artifacts": {"results_file": "engines/etl/parser/results/etl/..."},
  "attempt": 1
}
```

Each stage call records an immutable attempt and refreshes `latest.json` in the
run store (`artifacts/work/runs/<run-id>/stages/<stage>/`), and appends
`stage_started`/`stage_finished` to `events.jsonl`. Not a service-per-stage: one
`{stage}` path parameter dispatches to the matching pipeline adapter.
