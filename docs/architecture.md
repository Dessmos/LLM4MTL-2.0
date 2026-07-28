# LLM4MTL — Architecture (v5)

> Status: active v5 architecture. The migration plan is maintainer-only and
> intentionally git-ignored.

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

Established infrastructure also includes run_store/, experiment_store/,
stage_service/, external_tools/, serialization/ and workspace/. Planned
extensions are syntax_validation/, execution_evidence/, failure_diagnosis/,
feedback_refinement/, language_adapters/, ci_scenarios/ and a package-level
cli.py.

## Measurement layer (see `docs/measurement-spec.md`)

The evaluation layer is the measuring instrument for **test quality**: *can an
LLM generate semantic tests that detect additional, observable defects?* This is
the claim-critical spine and it drives the module boundaries below. The primary
metric is a mutation score over a frozen, qualified mutant set; details,
denominator, coherence gates and cost telemetry live in the measurement spec.
Boundaries are expected to fall out of that spec.

- `transformation_outcome_comparison/` — **the one true deep module**:
  language-agnostic, single source of truth for whether two transformation
  *outcomes* differ semantically (`≢`, over an outcome taxonomy, not byte
  compare). Reused by both mutant qualification and kill audit.
- mutation subsystem — mutation operators are **per-language** (they live in the
  per-language providers, making `language_adapters/` load-bearing: each language
  owns `{parse, execute, mutate, instrument}`); qualification + scoring is a
  **shared** module parameterised by language, built on the comparator.
- new task-level artifacts pinned in `manifest`: `mutation_catalog.json` (the
  qualified set `M_Q`), the versioned mutation-operator set, the versioned
  qualification corpus `Q`.
- cost seam — n8n **owns the fact** of each LLM call (tokens, latency; Python has
  no keys); the Python artifact layer **owns the evidence**, validating a typed
  `llm_call` event (`schemas/llm-call.schema.json`) and appending it to the run's
  `events.jsonl`, keyed `(run, stage, attempt)`. No side cost-log.

Facade convention (**target state, not yet enforced in code**): each deep package
should expose its public API from `__init__.py` (`__all__`); internals move under
`_internal/`. Per-package facade files carry a functional name (`validator.py`,
`executor.py`, `assembler.py`), never a generic `service.py`. Today only
`transformation_execution` is a real facade; `semantic_tests` exposes nothing and
no `_internal/` dirs exist yet. Per the measurement spec, facade polishing is
**frozen** until the measurement-driven boundaries settle; the convention is then
applied only to the modules that survive.

## Key invariants

- `contract.json` is generated from `.ecore` and defines **structural
  admissibility** only; the reference transformation is the behavioural oracle.
- `manifest.json` is immutable; run history is `events.jsonl`; stage evidence is
  `stages/<stage>/attempts/`.
- Routing lives only in n8n; Python returns `status` + `outcome_code` facts.
- A run = task + language + transformation model + test-generation model +
  strategy + seed + pipeline variant. Refinement iterations belong to the run.
- Significance is experiment-level, never per-run.
- The mutation-score denominator `M_Q` is built **before** any evaluated LLM test
  runs, from a versioned operator set + fixed qualification corpus `Q`; both
  versions are pinned in `manifest`. LLM tests never contribute to their own
  denominator.
- `transformation_outcome_comparison` is the **only** authority for semantic
  outcome difference; the numerator (test assertions) and denominator (comparator)
  must stay coherent — `assertion_comparator_mismatch` is a validity gate and must
  be 0.
- A mutant revealed only outside `Q` (`qualification_escape`) is published
  separately and may seed the next `Q`; it is **never** retro-added to the current
  denominator.
- LLM-call cost/latency is immutable run evidence in `events.jsonl` (fact owned by
  n8n, evidence owned by Python), never a side log.
