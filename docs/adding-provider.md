# Adding a new LLM / provider

> Status: **skeleton (Stage 0)**.

LLM generation is owned by n8n. Python never calls providers and never sees API
keys. Adding a model or provider is an n8n change.

New model of an existing provider:
1. Add it to the model selection in the n8n form.
2. Keep the same `generation-result.json` output shape.

New provider:
1. Add one language-neutral generation subworkflow under
   `workflows/n8n/subworkflows/generation/<provider>-generation.json`.
2. Register credentials inside n8n.
3. Emit the same `generation-result.json` (see `schemas/generation-result.schema.json`)
   and store the raw response in the standard location.

Python extraction, validation, codegen and evaluation do not change. The
provider-specific raw response may also be kept as `raw-response.json`, but no
downstream component may depend on its internal structure.
