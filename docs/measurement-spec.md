# LLM4MTL — Measurement Specification

> Status: **design spec (authoritative for the evaluation layer).** Module
> boundaries are expected to fall out of this document; where this spec and the
> current code disagree, this spec wins and the code is the debt.

## 0. What this project measures

Prior LLM4MTL generated **transformations**. This work generates **semantic
tests** for model transformations and asks: *can an LLM generate tests that are
good enough to detect additional semantic errors?*

The claim is **not** "we measure full semantic coverage" and **not** "we prove
transformation correctness". The claim is bounded: *generated tests detect
additional, observable semantic defects*. The whole evaluation layer is the
measuring instrument for **test quality under that bounded claim**, and its
primary design driver is **reproducibility / defensibility for a reviewer**, not
code aesthetics.

## 1. Metric hierarchy

| role | metric | what it answers |
| --- | --- | --- |
| **primary** | Adjusted Mutation Score over a frozen mutant set | do the tests *detect* observable semantic defects? |
| diagnostic | structural rule / branch coverage (where instrumentation is reliable) | do the tests *exercise* the reference behaviour? |
| reliability filter | executability, reference-pass rate | is a generated test trustworthy at all? |

Mutation score is primary. Coverage is **diagnostic only**, for two reasons: the
reference transformation is one implementation of the required behaviour (its
internal structure ≠ the task's semantics), and a test can exercise a rule
without asserting anything about the result. Divergence between mutation score
and coverage is **analysed, not treated as an error** (e.g. high coverage + low
mutation score can indicate weak assertions).

## 2. The denominator: the qualified mutant set `M_Q`

A coverage-style metric is meaningless without an explicit denominator. The
denominator is a **first-class, versioned, task-level artifact**, built **before
any evaluated LLM test runs**.

### 2.1 Mutation operators

- A **versioned, methodologically-defined set of mutation operators**.
- Operators are **per language** (mutating ETL source ≠ ATL ≠ QVTo ≠ Reactions).
- Their application to a reference transformation is **deterministic**.
- The operator-set version is pinned in the run `manifest`.

### 2.2 Observable mutants (`M_Q`)

A finite number of runs can never *prove* a mutant equivalent to the reference
for all possible inputs. We therefore never claim "proven non-equivalence"; we
claim **observable difference** on a fixed corpus.

```
M_Q = { m | parse(m) ∧ execute(m) ∧ ∃ x ∈ Q : O_m(x) ≢ O_ref(x) }
```

- `Q` — the **mutation qualification corpus**: independent, fixed **before** the
  experiment, versioned. May be built deterministically from metamodels + task
  contract + a fixed model-generation strategy, and/or reuse independent
  benchmark inputs.
- `≢` — **semantic** comparison of transformation *outcomes* (see §4), never a
  byte comparison of serialised files.
- `Q` is **separate from the evaluated generated tests**. LLM tests never
  contribute to their own denominator (that would be circular and inflate the
  score).

`M_Q` is persisted per task as `mutation_catalog.json`:

```
operator            # which mutation operator produced the mutant
changed_element     # the reference element that was mutated
source_hash         # hash of the pre-mutation reference version
syntactic_validity  # parse() result
executable          # execute() result
observable          # ∃ x ∈ Q : O_m(x) ≢ O_ref(x)
```

The catalog's content + version are pinned in the run `manifest`. If operators
or `Q` change, mutation scores are **not comparable across runs** — this pin is
what protects reproducibility (criterion #1).

## 3. The primary metric

Computed **strictly over the frozen `M_Q`**:

```
AdjustedMutationScore_Q =
    | { m ∈ M_Q | generated suite kills m } |
    ────────────────────────────────────────
                  | M_Q |
```

A mutant is **killed** iff the generated test suite **passes on the reference**
and **fails on the mutant**. Because the numerator is restricted to `m ∈ M_Q`,
it can never exceed the denominator by construction.

## 4. `transformation_outcome_comparison` — the shared source of truth

A single **language-agnostic deep module** is the only authority for "are two
transformation outcomes semantically different". It operates at the level of the
target metamodel / EMF outcome, **not** the transformation language — so
mutation operators are per-language while this comparator is shared.

- Interface (narrow): `diff(outcome_a, outcome_b, target_metamodel) -> outcome_diff`.
- Implementation (deep): element matching by structural identity (not by
  generated id), order-independence for unordered references, containment
  awareness, canonicalisation.
- **Outcome taxonomy** — an outcome is not always "a successful target model":
  `success+model` / `compile-fail` / `runtime-exception` / `empty-output`. `≢`
  is defined across outcome *types*, not only between two models.

This is the one place where the "deep modules" goal genuinely pays rent: large
implementation behind a narrow interface, reused in both qualification (§2.2)
and kill audit (§5).

## 5. Coherence: numerator vs denominator use different comparisons

The **denominator** uses the full comparator `≢`. The **numerator** uses whatever
**assertions the LLM wrote**. This asymmetry is intended — we are measuring
whether the tests catch what is observably different. It creates two audited
outcomes.

### 5.1 Confirmed kill

```
confirmed kill ⟺
    test passes on reference
  ∧ test fails on mutant
  ∧ shared comparator confirms a behavioural difference
    on the same input the test used
```

### 5.2 `assertion_comparator_mismatch` (validity failure — must be 0)

For every test that passes on reference and fails on mutant `m`, re-audit on the
**same input `x`** the test used: compare `O_ref(x)` vs `O_m(x)` with the shared
comparator.

- outcomes differ → **kill confirmed**;
- outcomes are equivalent under the comparator, yet the assertion still fails →
  **`assertion_comparator_mismatch`**: the test oracle and the shared comparator
  disagree on the same input.

This kill is **not counted**, and the run is flagged incoherent. For a fully
coherent experiment `assertion_comparator_mismatch == 0`. This count is
published as a validity guarantee.

### 5.3 `qualification_escape` / `newly_observed_mutant` (a result, not a bug)

A mutant may sit outside `M_Q` for two different reasons: the comparator missed a
difference, **or** `Q` simply contained no input that reveals it. The second case
is a **potential headline result**: a generated test may synthesise a new input
`x_g ∉ Q` and reveal `O_m(x_g) ≢ O_ref(x_g)` — behaviour the benchmark corpus did
not cover. That is exactly the bounded claim (detecting *additional* defects).

Such an event is **never retro-added to the current denominator** (that would make
the denominator depend on the evaluated tests). It is recorded separately:

```
qualification_escape_count
newly_observed_mutant_ids
revealing_generated_test_ids
revealing_input_model_ids
```

These may feed the **next versioned** `Q`, not the current experiment's score.

## 6. Cost / effort telemetry (model ↔ quality ↔ cost)

A stated deliverable is the dependence of **model → test quality → cost** (tokens
and wall-clock time). Under the architecture invariant, **all LLM calls happen in
n8n; Python holds no API keys**, so token counts and latency are known only to
n8n.

Two distinct ownerships:

- **fact ownership** — n8n observes the concrete LLM call and forms the telemetry;
- **evidence ownership** — the Python artifact layer validates the event and
  appends it to the run's append-only journal.

Therefore:

- a single authoritative store: the run's `events.jsonl` (no side CSV, no
  parallel cost-log — a second source of truth breaks reproducibility);
- n8n emits a typed `llm_call` event through the same `stage_service` ingest;
- schema `schemas/llm-call.schema.json`, keyed `run_id / stage / attempt`;
- fields: `model`, `prompt_tokens`, `completion_tokens`, `latency_ms`,
  `cost_estimate`.

The `(run, stage, attempt)` key is mandatory: quality is measured on a specific
generation's suite; cost is per LLM call; correlating model↔quality↔cost requires
both facts on the same key. Refinement matters here — each iteration costs tokens,
and cost must be attributed to the **exact attempt** whose tests were scored.

## 7. Architectural consequences (boundaries this spec re-cuts)

- **`transformation_outcome_comparison/`** — new shared deep module; single
  source of truth for `≢`.
- **mutation subsystem** — operators live in per-language providers
  (`language_adapters/*` becomes load-bearing: each language owns
  `{parse, execute, mutate, instrument}`); qualification + scoring is a shared
  module parameterised by language, built on the comparator.
- **`execution`** gains two passes: reference×mutant (builds `M_Q`) and
  suite×mutant (kill).
- **`evaluation`** gains a new aggregation axis: *a test across the mutant set*,
  not only per-run metrics.
- **`benchmark`** gains new inputs: the mutant corpus and `Q`.
- new task-level artifacts pinned in `manifest`: `mutation_catalog.json`,
  operator-set version, `Q` version.
- new validity outputs: `assertion_comparator_mismatch` (gate == 0),
  `qualification_escape` (published separately).

## 8. Sequencing

1. This spec is authoritative first; **facade / `_internal/` polishing is frozen**
   until the boundaries below settle.
2. Module boundaries fall out of §4–§7.
3. Only the modules that survive get the facade convention applied — then
   `_internal/` and `__all__` stop being aspirational.
