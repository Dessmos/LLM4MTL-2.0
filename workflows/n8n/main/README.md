# LLM4MTL agent workflow (master)

`llm4mtl-agent-workflow.json` is the orchestration workflow, not a scaffold. One
user-facing workflow, one Start button; internally it executes the existing
prompting subworkflows through `Execute Sub-workflow` and the deterministic
stages through the **stage service** (`pipeline/stage_service/`).

n8n is the control plane: it owns provider/model selection, credentials, LLM
calls, routing, and iteration limits. Python does the deterministic work and
returns facts, never routing decisions.

## Configuration flow

A run is configured on **one screen, behind one link**. The `Configure and Start
Pipeline` form trigger collects the whole configuration and hands it straight to
the queue builder:

```text
Configure and Start Pipeline  ->  Validate Config and Build Run Queue  ->  State Machine
```

Every choice is a native n8n `radio` or `checkbox` group, presented as selectable
cards through the node's own **Custom Form Styling** (`options.customCss`). The
markup is n8n's: each option is still its own input plus its label, the input is
stretched transparently over the card, and n8n's single-select and multi-select
behaviour is untouched. Nothing in the form is a custom control — n8n forms only
submit native inputs, and an HTML element drawn as a button would return no usable
value.

The trigger is on **typeVersion 2.5**, and that is load-bearing rather than
incidental: n8n's `getFieldIdentifier` only keys a submitted field by its
`fieldName` from 2.4 on. Below that the same form posts `{"Run mode": "Full
Pipeline"}` and every name the queue builder reads arrives undefined. The tests
submit through that same rule, so a downgrade fails the suite instead of the run.

The screen is ordered as the five sections below. Fields belonging to a branch the
selected run mode does not execute stay visible and are simply ignored, because
what a run may leave unconfigured is decided in validation, not by hiding fields.

### 1. What is being run

* **Run mode** — three cards, each with a one-line summary of what it executes:
  `Semantic Tests Only`, `Transformations Only`, `Full Pipeline`. Recorded as
  `config.run_mode` = `tests_only` / `transformations_only` / `full`.
* **Languages** — ETL, ATL, QVT-O, Reactions; at least one.

### 2. Tasks

One card list per language. The names are the task contracts under
`benchmark/tasks/<language>/task_contracts`, which is the authoritative source;
every selected language needs at least one task, and a list for a language that
was not selected is ignored. There is no hidden default task.

### 3. LLM roles

The provider for each of the four roles — OpenAI, Anthropic, or Google Gemini.
Providers only: see below for where the exact model comes from.

### 4. Prompting strategies

Each branch has its own strategy, as four cards. The card shows the reading name
and the run records the canonical id, which is what the variant workflows are
named after:

| card | recorded id |
| --- | --- |
| Prompt only | `only_prompt` |
| Few-shot | `few_shot` |
| Grammar | `grammar` |
| Few-shot + Grammar | `few_shots_AND_grammar` |

The semantic-test and transformation strategies are independent; the one belonging
to a branch this run mode does not execute is ignored.

### 5. Experiment and ablation

Refinement iterations (0–5, bounding both branches), plus the RQ4 configuration:
a named profile
(`Standard full configuration`, `No parser feedback`, `No semantic feedback`,
`No failure diagnosis` — the variants under `experiments/variants/`) or `Custom
ablation` with an explicit component list. A named profile refuses an extra
component selection rather than applying an ablation its variant id does not
name.

## Provider selection versus model selection

```text
form chooses provider
        v
master chooses the matching configured AI Model node
        v
exact model is read from that node's built-in selector
```

The form selects **providers only**. The exact model and the n8n credential stay
in the built-in selector of the standard AI Model nodes on the canvas:

```text
Transformation Generation   - {OpenAI, Anthropic, Google Gemini} Chat Model
Semantic Test Generation    - {OpenAI, Anthropic, Google Gemini} Chat Model
Source Diagnosis            - {OpenAI, Anthropic, Google Gemini} Chat Model
Refinement                  - {OpenAI, Anthropic, Google Gemini} Chat Model
```

Those selectors are the provider's own model list, so the master never carries
one of its own.

The artifact tree is one directory per **model family**, not per exact model id:
every `gpt-5` variant writes under `gpt-5`, every `claude-sonnet-4` variant under
`claude-sonnet-4`, every `gemini-2.5-pro` variant under `gemini-2-5-pro`. The
family is read from the variant workflow that was selected, which already
declares it. The exact id reaches the n8n model node and remains in the master's
LLM configuration; `POST /runs` receives the stable family id that Python uses
for generated-suite identity and selection. Raw responses are selected from the
run- and artifact-iteration-scoped path instead. All twelve nodes
stay connected to `Validate Config and Build Run Queue` through
`ai_languageModel`, which is how `selectedModel()` reads them with
`$(nodeName).params`.

A role is resolved **only when the final configuration can reach it**, so a
tests-only run does not demand a transformation model, and a run with failure
diagnosis ablated does not demand a diagnosis model. Reachability is:

| role | reachable when |
| --- | --- |
| `semantic_test` | mode runs tests **and** `test_generation` enabled |
| `transformation` | mode runs transformations **and** `transformation_generation` enabled |
| `source_diagnosis` | mode is `full` **and** `semantic_execution` **and** `source_diagnosis` enabled |
| `refinement` | iterations > 0 **and** a reachable branch has its refinement enabled |

A role that *is* reachable still fails loudly when its AI Model node has no model
selected.

## Run modes

`run_mode` is which pipeline the user intends to execute. The stage flags are
which components of that pipeline are enabled or ablated. They are separate axes
and both are recorded — `full` with failure diagnosis ablated is a different
experiment from `transformations_only`.

```text
tests_only
  generate_tests -> extract -> technical -> reference -> final
  terminal: completed / TESTS_ONLY_PIPELINE_COMPLETE
  never routes into transformation generation

transformations_only
  generate_transformations -> syntax (-> parser-feedback refinement) -> final
  terminal: completed / TRANSFORMATIONS_ONLY_PIPELINE_COMPLETE
  never routes into semantic-test generation, and adds no semantic execution

full
  TEST BRANCH             generate_tests -> extract -> technical -> reference
                                                                        \
                                                                    execution
                                                                        /
  TRANSFORMATION BRANCH   generate_transformations -> syntax
  terminal: completed / SEMANTIC_PASSED
```

On `SEMANTIC_EXECUTION_FAILED` the full pipeline diagnoses the source. One
execution attempt can fail several suite/transformation pairs, so the master
routes on the whole prepared set rather than on one report:

```text
SEMANTIC_EXECUTION_FAILED
        -> artifacts.failure_report_index      (Python names every prepared report)
        -> Read Diagnosis Index
        -> every report with status "created" and source_diagnosis.eligible true
        -> one diagnosis subworkflow call per report, each persisting its verdict
        -> Aggregate
        -> refinement routing
```

Python decides which reports are diagnosable; how many diagnoses that implies and
how the verdicts combine is routing, and stays in n8n. `failure_report_path`
remains a backward-compatible shortcut to the first diagnosable report, and the
master no longer routes on it.

Aggregation is conservative and deliberately not a majority vote:

| individual verdicts | aggregate |
| --- | --- |
| only `transformation_defect` | `transformation_defect` -> transformation refinement |
| only `test_defect` | `test_defect` -> test refinement |
| any `ambiguous` | `ambiguous` -> stop |
| both defect kinds | `ambiguous` -> stop |

`T, T, X` is ambiguous. A majority would repair the transformation while the
evidence still says a test may be at fault, which is the mistake source diagnosis
exists to prevent. Terminal reasons for the cases that decide nothing:

```text
NO_ELIGIBLE_SOURCE_DIAGNOSIS_REPORTS   the attempt prepared evidence, none diagnosable
INCOMPLETE_SOURCE_DIAGNOSIS_SET        a verdict is missing; a partial set decides nothing
AMBIGUOUS_SOURCE_DIAGNOSIS             the set disagrees or one report was ambiguous
```

Both prepared report types are diagnosable: `semantic_test_case_failure` names the
failing case and assertion, and `semantic_execution_pair_failure` is the failure
that happened before any test method ran, so it names neither and carries the
whole suite. The diagnosis subworkflow normalizes both to one input and reports
which it read as `scope` (`test_case` / `execution_pair`).

The State Machine filters every candidate action through the mode before the
stage flags. When nothing left is in the mode's scope and the pipeline actually
ran, that is the mode's successful terminal point; a stage that is merely ablated
keeps the existing `incomplete` reason.

## Orchestration core

```text
State Machine -> Route Next Action -> action -> Capture Action Result -> State Machine
```

Unchanged, and deliberately compact — one Switch and one loop rather than a
duplicated IF graph per stage. `Create Immutable Run`, the Python stage HTTP
calls, `Make Existing Workflow Callable` (exact strategy-suffix matching and the
reserved `/responses/source-diagnosis/` namespace), timeline recording, terminal
statuses and refinement limits all stay as they were.

`Adapt Transformation Workflow Compatibility` operates only on the transient
workflow JSON passed to `Execute Existing Subworkflow`. For both generation
branches it narrows the prompt reader to the selected task and makes the raw
response run- and artifact-iteration-scoped. For transformations it additionally
preserves the `binary.data` that legacy Set nodes passed through before n8n 2.x.
The external workflow exports on disk are not edited, and non-generation
subworkflows are returned unchanged.

There is one master workflow. Run modes are configuration, not three copies.

## Recorded configuration

`config` carries the full experimental identity: `run_mode`, `llms` (per role:
provider, exact model, `configuration_node`, and strategy where applicable),
`max_refinement_iterations`, the twelve effective `stages` flags,
`ablation_profile`, `disabled_stages`, and `pipeline_variant`.

`pipeline_variant` is `run_mode` when nothing is ablated and
`run_mode:ablation-id` otherwise, so a standard full run keeps the plain `full`
that earlier runs recorded:

```text
full
full:no-failure-diagnosis
tests_only
transformations_only:custom:parser_feedback+semantic_feedback
```

Each queue entry is one `language × task`; runs execute sequentially. A run mode
without a branch records `null` for that branch's model and strategy axes, which
is what `schemas/manifest.schema.json` means by "not applicable to the stages
this run executes". Null is never "any value": a stage that needs a null axis
refuses.

## Stage contract

1. **Create Run** — `POST http://stage-service:8129/runs` → `{run_id}`.
2. **Generation** (n8n owns it) — the provider subworkflow calls the LLM and
   writes the raw response into the run-specific response directory. The
   repository's `generation-result.schema.json` is not currently persisted by
   these workflows.
3. **Stages** — `POST /runs/{run_id}/stages/{stage}`; n8n reads
   `{status, outcome_code, artifacts}` and routes on it.

`docs/n8n-python-contract.md` is authoritative for stage ids and
`outcome_code` values.

## Code nodes and the n8n sandbox

n8n runs Code nodes in a vm2 `NodeVM` — a fresh V8 context with the JavaScript
built-ins and none of Node's own globals. `structuredClone`, `fetch`, `URL`,
`TextEncoder` and `crypto` are all absent there while working fine under plain
`node`, so a Code node must stay within the language built-ins (`JSON`, `Object`,
`Set`, `Map`, `Buffer`, `setTimeout` and the standard prototypes are available).
`pipeline/tests/fixtures/run_master_code_node.js` evaluates in a `node:vm` context
configured to that same surface, so a Code node that cannot run in n8n cannot pass
the tests either.

## Known limitations

* n8n form fields are static definitions in the workflow JSON, so the task lists
  are checked in rather than read from `benchmark/` at form-render time.
  `pipeline/tests/test_master_run_modes.py` asserts the form's options equal the
  task contracts on disk, so adding a contract fails the suite instead of
  silently becoming unselectable.
* Fields are not conditionally shown or hidden: a tests-only run still displays
  the transformation strategy, and its value is then ignored. n8n form fields have
  no conditional disclosure, so which roles a run actually requires is enforced in
  validation, where it has to be correct anyway.
* One screen means one long screen — the full configuration is roughly 3700px
  tall with every language expanded. That is the trade for a single link and a
  single node, and the numbered sections carry the structure the pages used to.
* Ablating a stage in the middle of a mode's pipeline still terminates
  `incomplete` with the stage-specific reason, as it did before run modes
  existed.
