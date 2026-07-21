# Runner API

> Status: **skeleton (Stage 0)**. Implemented in Stage 5 (`pipeline/runner/`).

The runner is a thin FastAPI service wrapping the `llm4mtl` CLI, deployed next to
n8n in a container that has Python + JDK + Maven + engines. It is transport only;
no business logic.

```http
POST /runs                              → 200 {run_id, status: "initialized"}
POST /runs/{run_id}/stages/{stage}      → 202 {status: "running"}
GET  /runs/{run_id}/stages/{stage}      → 200 <stage-result.schema.json>
GET  /runs/{run_id}                     → 200 {run_id, status, stages: [...]}
```

Same implementation surface as manual use: `POST /runs/{id}/stages/{stage}`
dispatches into the exact `llm4mtl stage <stage>` CLI command a developer runs by
hand. Not a service-per-stage: one `{stage}` path parameter.
