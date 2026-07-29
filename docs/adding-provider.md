# Adding an LLM model or provider

> Status: current ownership contract. The remaining Python allowlists are
> recorded implementation debt.

LLM invocation is owned by n8n. Python never holds provider credentials and
never calls an external LLM API. Python receives only normalized facts and
artifacts.

## New model on an existing provider

1. Add the model to the appropriate n8n selection and provider mapping.
2. Preserve the normalized `generation-result.json` shape defined by
   `schemas/generation-result.schema.json`.
3. Record the concrete provider and model names; do not infer them later from a
   directory or workflow name.
4. Verify that the exported workflow contains no credentials.

Current compatibility note: `experiment_runner/config.py` still validates model
names through `ALLOWED_MODELS`. Until that allowlist is moved to n8n-owned data,
adding a model also requires updating it and its tests. Python uses this only as
validation; it does not select the provider or model.

## New provider

1. Add a language-neutral provider branch or generation subworkflow under
   `workflows/n8n/`.
2. Store credentials only in n8n credential storage or approved environment
   configuration.
3. Normalize provider-specific output before it crosses into Python.
4. Emit the same artifact and telemetry fields as existing providers.
5. Preserve the provider's raw response only as audit evidence; downstream code
   must not depend on its private shape.

Failure diagnosis currently accepts `openai`, `anthropic`, and `google` in both
`stage_service/api_models.py` and `schemas/diagnosis.schema.json`. Adding a
diagnosis provider therefore requires updating those two validation contracts
until the provider registry is made data-driven.

## Boundary invariants

- Provider selection, credentials, LLM retries, and raw provider mappings stay
  in n8n.
- Python owns schema validation, artifact persistence, deterministic processing,
  and factual stage outcomes.
- Provider code must not be duplicated per transformation language.
- No API key, authorization header, or credential identifier may be written to
  source, workflow exports, logs, or run artifacts.
- Routing remains in n8n; provider subworkflows do not emit Python
  `next_action` decisions.

Cost/token telemetry is specified in `measurement-spec.md`. Its target
authoritative store is the run's append-only event journal; the ingest contract
is not implemented yet.
