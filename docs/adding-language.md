# Adding a new MTL language

> Status: **skeleton (Stage 0)**.

A new language does NOT copy the pipeline. Touch points:

Required:
- `engines/<lang>/parser/` and `engines/<lang>/harness/` (Java/Maven).
- `pipeline/llm4mtl/languages/<lang>.py` — capability-based adapter (bindings:
  `parser_engine`, `harness_engine`, formats, `prepare_engine_inputs`,
  `capabilities`). NOT a God object; the stage owns the use case.
- `benchmark/tasks/<lang>/<task>/` — task inputs.
- `prompt_assets/{tests,transformations}/.../<lang>/` — hand-authored material.

Possibly:
- a new deterministic code generator, or a new validation capability.

Must NOT be required:
- changes to provider generation subworkflows (they are language-neutral),
- changes to existing stage implementations,
- a `language ==` switch in the n8n main workflow.

If provider workflows need editing per language, language knowledge has leaked
across the wrong boundary.
