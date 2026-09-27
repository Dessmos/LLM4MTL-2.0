# Model selection

Decided 2026-09-27: one model per provider, matched in capability rather than
each provider's flagship.

| Provider | Model | Reasoning effort |
| --- | --- | --- |
| OpenAI | GPT-5.6 Luna (`gpt-5.6-luna`) | xhigh |
| Google | Gemini 3.7 Flash | medium |
| Anthropic | Claude Sonnet 5 | xhigh |

The model and the effort are set on the role's AI Model node in the master
workflow; see [workflows/n8n/main/README.md](../workflows/n8n/main/README.md).
Every run records them in `batch.json` under `config.llms.<role>`.

Current support in the pipeline:

- OpenAI: model and effort reach every call (Responses API).
- Google and Anthropic: the master reads a reasoning effort from OpenAI nodes
  only, so these models currently run at the provider's default effort. Their n8n credentials are also not yet configured.
