# Model selection

Decided 2026-09-27: one model per provider, matched in capability rather than
each provider's flagship.

| Provider | Model | Reasoning effort |
| --- | --- | --- |
| OpenAI | GPT-5.6 Luna (`gpt-5.6-luna`) | xhigh |
| Google | Gemini 3.7 Flash | medium |
| Anthropic | Claude Sonnet 5 | xhigh |

Each model is picked in the role's AI Model node in the master workflow. The
OpenAI effort is that node's Reasoning Effort option; the Claude effort and the
Gemini thinking level are fields of the launch form. See
[workflows/n8n/main/README.md](../workflows/n8n/main/README.md). Every run
records model and effort in `batch.json` under `config.llms.<role>`, and each
call's served model, token counts, and latency as `llm_call_observed` events.

How the calls are made:

- OpenAI: called directly on the Responses API with the n8n OpenAI credential.
- Anthropic and Google: called through LiteLLM's pass-through routes
  (`/anthropic/v1/messages`, `/gemini/v1beta/models/<id>:generateContent`),
  which return the provider's own response. Their n8n credentials (Anthropic,
  Google Gemini) hold the LiteLLM key, and their ids go into
  `PROVIDER_CREDENTIALS` in `prompt_assembly/n8n_exports/workflow_graph.py`
  before the exports are regenerated; neither credential exists yet. The
  proxy's address is `LITELLM_BASE_URL` in `Adapt Subworkflow For This Run`.
