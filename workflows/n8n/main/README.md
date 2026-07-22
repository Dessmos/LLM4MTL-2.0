# LLM4MTL agent workflow (master)

One user-facing workflow, one Start button. Internally it uses reusable
subworkflows (`Execute Sub-workflow`) — for the user it is still a single
workflow. n8n is the control plane: it owns provider/model selection, credentials,
LLM calls, routing, and iteration limits. Python does the deterministic work,
reached through the **stage service** (`pipeline/stage_service/`).

> `llm4mtl-agent-workflow.json` here is a **minimal importable scaffold** (Start →
> Create Run → first stage call). The full agent below is authored in the n8n
> editor because a complete workflow JSON cannot be verified headless. This README
> is the authoritative design.

## Configuration (form at the top of the master workflow)

```json
{
  "language": "etl",
  "task": "Tree2Graph",
  "operation": "full_pipeline",
  "provider": "openai",
  "model": "gpt-5",
  "strategy": "few_shot",
  "transformation_model": "claude-sonnet-4",
  "max_syntax_repairs": 2,
  "max_semantic_repairs": 2
}
```

The API key never enters this object — it stays in n8n credentials.

## Flow

1. **Create Run** — `POST http://stage-service:8129/runs` → `{run_id}`.
2. **Generation** (n8n owns it) — the provider subworkflow calls the LLM and writes
   the raw response + `generation-result.json` into the run.
3. **Stages** — each is `POST /runs/{run_id}/stages/{stage}`; n8n reads
   `{status, outcome_code, artifacts}` and routes via a Switch node.

## Transition table (Switch on `outcome_code`) — lives in n8n only

| stage | outcome_code | next |
| --- | --- | --- |
| extract | `EXTRACTED` / `TEST_SPEC_INVALID` | technical-validation / regenerate test |
| syntax-validation | `SYNTAX_VALID` / `SYNTAX_INVALID` | continue / repair transformation |
| technical-validation | `TECH_VALID` / `TECH_COMPILE_FAILED` | reference-validation / repair test |
| reference-validation | `REFERENCE_VALIDATED` / `REFERENCE_VALIDATION_FAILED` | execution / test defect |
| execution | `SEMANTIC_PASSED` / `SEMANTIC_EXECUTION_FAILED` | evaluate / diagnose |
| (any) | `INFRASTRUCTURE_ERROR` | retry / stop (n8n policy) |

Iteration limits (`max_*_repairs`) and stop conditions are n8n policy.

## Subworkflows

```text
subworkflows/generation/{openai,anthropic,google,local}-generation.json  (language-neutral)
subworkflows/validation/{syntax-validate,tests-technical,tests-reference}.json
subworkflows/execution/execute.json
subworkflows/diagnosis/llm-diagnosis.json       (LLM call in n8n; Python prepares evidence)
subworkflows/refinement/refine.json
subworkflows/reporting/build-report.json
```
