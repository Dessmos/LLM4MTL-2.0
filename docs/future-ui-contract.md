# Future UI contract

> Status: reserved boundary. No UI is implemented, and UI work must not move
> orchestration or credentials out of n8n.

A future UI stays thin and talks to n8n, not directly to Python or Maven:

```text
UI
  → POST n8n workflow webhook with one run identity
  ← {run_id, status}

UI
  → poll/query run status
  ← immutable manifest + stage names + canonical latest attempt results
```

The submitted identity must fix one concrete:

```text
language
task
transformation model and strategy
test-generation model and strategy
seed
pipeline variant
```

The UI may also expose bounded attempt-specific controls such as a `suite_id`,
but it must not send identity overrides with a stage request. Matrix expansion
for several tasks/models/strategies belongs in n8n or an experiment-definition
surface before individual runs are created.

The UI never:

- holds provider credentials;
- invokes an LLM, parser, Maven, or Python subprocess;
- writes files into `artifacts/` or `engines/`;
- interprets engine logs as domain outcomes;
- chooses the next workflow transition from Python internals.

n8n remains responsible for provider calls, retries, routing, and iteration
limits. The stage service remains transport-only and exposes factual
`status`/`outcome_code` results.

Until a UI exists, n8n's form/webhook is the user-facing control surface. A
future implementation should live under an application directory such as
`apps/experiment-ui/`; do not create a top-level placeholder or couple the
current pipeline to a hypothetical frontend.
