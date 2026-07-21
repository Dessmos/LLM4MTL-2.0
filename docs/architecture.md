# LLM4MTL — Architecture (v5)

> Status: **skeleton (Stage 0)**. Content is filled in during the migration.
> The staged migration plan is maintainer-only in `docs/migration-plan.md`
> (git-ignored).

## Layers and ownership

```text
UI (later)   → parameters + status display (one n8n webhook)
n8n          → control plane: config, language/task/model/strategy selection,
               credentials, LLM calls, agent routing, iteration limits
Python (CLI) → deep modules: extraction, deterministic JUnit codegen, validation,
               execution, diagnosis evidence, evaluation. No API keys.
engines/     → language-specific parsing/execution behind Python facades
artifacts/   → immutable per-run history
```

## Top-level areas

- `schemas/` — single source of truth for all artifact JSON schemas.
- `engines/` — Java/Maven parsers and test harnesses per language (moved as-is).
- `pipeline/` — the Python subsystem. Uses a `src/` layout: the importable
  package is `pipeline/src/llm4mtl/`, tests are `pipeline/tests/`, and the
  `stage_service/` HTTP wrapper lives alongside.
- `benchmark/` — hand-authored task inputs (metamodels, reference, fixtures, contract).
- `prompt_assets/` — hand-authored LLM material (templates, few-shot, grammar).
  Distinct from `prompt_assembly/` (the Python code that assembles a prompt) and
  from the runtime `prompts/` produced per run.
- `workflows/n8n/` — the n8n control plane (one master workflow + subworkflows).
- `experiments/` — presets, ablation variants, run matrices.
- `artifacts/` — generated output (`work/` git-ignored; `published/` frozen).

## Python package layout (`pipeline/src/llm4mtl/`)

Names describe domain responsibility, not technical form. Established so far:

- `task_contracts/` — the deterministic task `contract.json` derived from `.ecore`.
- `prompt_assembly/` — assembles a production prompt from contract + reference + template.
- `semantic_tests/` — extraction, `codegen` (renders a JUnit harness — *not*
  compilation), technical_validation, reference_validation, shared `suites/`.
- `transformation_execution/` — runs reference-validated suites against generated
  transformations (was `transformation_validation`; renamed to avoid a three-way
  clash with technical/reference *validation*, which validate the tests).
- `evaluation/` — run metrics + experiment-level aggregation/significance.
- `serialization/` (CSV/JSON), `external_tools/` (Maven subprocess), `workspace/`
  (isolated engine copy + injection) — infrastructure.
- `experiment_runner/` — local orchestration glue and CLI; production orchestration
  is n8n.

Planned for later stages (names fixed now): `syntax_validation/`,
`execution_evidence/` (normalizes Maven/JUnit output), `failure_diagnosis/`
(prepares/validates the LLM diagnosis; the LLM call stays in n8n),
`feedback_refinement/`, `language_adapters/` (`interfaces.py` + `registry.py`),
`ci_scenarios/` (linear CI runner, no routing), `run_store/`, `identifiers.py`,
`cli.py`, and `stage_service/`.

Facade convention: each deep package exposes its public API from `__init__.py`
(`__all__`); internals move under `_internal/`. Per-package facade files carry a
functional name (`validator.py`, `executor.py`, `assembler.py`), never a generic
`service.py`.

## Key invariants

- `contract.json` is generated from `.ecore` and defines **structural
  admissibility** only; the reference transformation is the behavioural oracle.
- `manifest.json` is immutable; run history is `events.jsonl`; stage evidence is
  `stages/<stage>/attempts/`.
- Routing lives only in n8n; Python returns `status` + `outcome_code` facts.
- A run = task + language + transformation model + test-generation model +
  strategy + seed + pipeline variant. Refinement iterations belong to the run.
- Significance is experiment-level, never per-run.
