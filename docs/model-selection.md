# Model selection

Decided 2026-09-27: one model per provider, matched in capability rather than
each provider's flagship. Revised 2026-09-30: Claude and Gemini are served by the
KIT LiteLLM proxy, which offers Gemini 3.8 Flash, not 3.7 Flash, at the same
price.

| Provider | Model | Reasoning effort |
| --- | --- | --- |
| OpenAI | GPT-5.6 Luna (`gpt-5.6-luna`) | xhigh |
| Google | Gemini 3.8 Flash (`google.gemini-3.8-flash`) | medium |
| Anthropic | Claude Sonnet 5 (`google.claude-sonnet-5`) | xhigh |

The `google.` ids are the proxy's names; it serves both models from Vertex AI.
Revised 2026-10-20: Claude and Gemini are called directly on the providers' own
APIs, no longer through the proxy. The `google.` ids above are what the runs
before that date requested; a direct call needs the provider's own model id.

Each model is picked in the role's AI Model node in the master workflow. The
OpenAI effort is that node's Reasoning Effort option; the Claude effort and the
Gemini thinking level are fields of the launch form. See
[workflows/n8n/main/README.md](../workflows/n8n/main/README.md). Every run
records model and effort in `batch.json` under `config.llms.<role>`, and each
call's model, token counts, and latency as `llm_call_observed` events.

How the calls are made:

- OpenAI: called directly on the Responses API with the n8n OpenAI credential.
- Anthropic and Google: called directly on their own APIs
  (`https://api.anthropic.com/v1/messages`,
  `https://generativelanguage.googleapis.com/v1beta/models/<id>:generateContent`)
  in `Adapt Subworkflow For This Run`, so `served_model` is the version the
  provider reports and `litellm_model_name` is null. Their n8n credentials
  (Anthropic, Google Gemini) hold the provider's own API key, and their ids go
  into `PROVIDER_CREDENTIALS` in
  `prompt_assembly/n8n_exports/workflow_graph.py` before the exports are
  regenerated.
