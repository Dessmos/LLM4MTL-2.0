# Future UI contract

> Status: **skeleton (Stage 0)**. UI is out of current scope; the seam is
> reserved so it can be added later without changing the pipeline.

A future UI stays thin and talks to a single n8n webhook:

```text
UI  → POST /workflow/start {language, task, model, strategy, operation, limits}
    → {run_id, status: "running"}
UI  → GET  /runs/{run_id}     (poll or events)  → per-stage status
```

The UI never runs Python or Maven and never holds provider credentials. Until it
exists, n8n's own form + webhook is the interim user interface. When built, it
would live under `apps/experiment-ui/` (not a top-level `ui/` folder created
prematurely).
