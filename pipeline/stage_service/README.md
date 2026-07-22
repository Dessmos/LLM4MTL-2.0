# Stage service

A thin FastAPI wrapper (transport only, no business logic) that lets n8n drive the
pipeline. The service code lives in the package at
`pipeline/src/llm4mtl/stage_service/`; this directory holds only the deployment
(Dockerfile + compose).

## Endpoints

```http
GET  /health                              -> {"status": "ok"}
POST /runs                                -> {"run_id", "status": "initialized"}
POST /runs/{run_id}/stages/{stage}        -> <stage-result payload>
GET  /runs/{run_id}/stages/{stage}        -> latest stage result (n8n's projection)
GET  /runs/{run_id}                       -> {"run_id", "manifest", "stages": [...]}
```

`{stage}` is a contract stage id: `extract`, `syntax-validation`,
`technical-validation`, `reference-validation`, `execution`. The stage-result
payload is `{schema_version, stage, status, outcome_code, counts, artifacts,
attempt}` — Python reports facts; routing lives in n8n (see
`docs/n8n-python-contract.md`).

## Run locally (dev)

```bash
.venv/bin/python -m uvicorn llm4mtl.stage_service.app:app --port 8129
```

## Run in Docker (with engines + Maven)

```bash
docker compose -f pipeline/stage_service/docker-compose.yml up -d --build
curl -s -X POST http://localhost:8129/runs -H 'content-type: application/json' \
  -d '{"run_id":"demo","language":"etl","task":"Tree2Graph"}'
curl -s -X POST http://localhost:8129/runs/demo/stages/syntax-validation \
  -H 'content-type: application/json' \
  -d '{"tasks":["Tree2Graph"],"transformation_models":["claude-sonnet-4"],"transformation_strategies":["grammar"]}'
```
