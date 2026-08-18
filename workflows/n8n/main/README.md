# LLM4MTL agent workflow (master)

`llm4mtl-agent-workflow.json` is the orchestration workflow, not a scaffold. One
user-facing workflow, one Start button; internally it executes the existing
prompting subworkflows through `Execute Sub-workflow` and the deterministic
stages through the **stage service** (`pipeline/stage_service/`).

n8n is the control plane: it owns provider/model selection, credentials, LLM
calls, routing, and iteration limits. Python does the deterministic work and
returns facts, never routing decisions.

## Configuration flow

Configuration is a four-screen n8n form. The trigger is the first screen and
each following screen is an `n8n-nodes-base.form` page (`operation: page`); the
pages run in a fixed order and the queue is built from all four.

Every choice is a native n8n `radio` or `checkbox` group, presented as selectable
cards through the nodes' own **Custom Form Styling** (`options.customCss`). The
markup is n8n's: each option is still its own input plus its label, the input is
stretched transparently over the card, and n8n's single-select and multi-select
behaviour is untouched. Nothing in the form is a custom control — n8n forms only
submit native inputs, and an HTML element drawn as a button would return no usable
value. All four screens share one stylesheet so they cannot drift apart.

```text
Run Setup  ->  Semantic Test Configuration  ->  Transformation Configuration
           ->  Experiment and Ablation      ->  Validate Config and Build Run Queue
           ->  State Machine
```

### 1. Run Setup

* **Run mode** — three cards, each with a one-line summary of what it executes:
  `Semantic Tests Only`, `Transformations Only`, `Full Pipeline`. Recorded as
  `config.run_mode` = `tests_only` / `transformations_only` / `full`.
* **Languages** — ETL, ATL, QVT-O, Reactions; at least one.
* **Tasks** — one checkbox list per language. The names are the task contracts
  under `benchmark/tasks/<language>/task_contracts`, which is the authoritative
  source; every selected language needs at least one task. There is no hidden
  default task.
* **Providers** — OpenAI / Anthropic / Google Gemini for each of the four LLM
  roles.

### 2. Semantic Test Configuration

The semantic-test prompting strategy, as four cards. The card shows the reading
name and the run records the canonical id, which is what the variant workflows are
named after:

| card | recorded id |
| --- | --- |
| Prompt only | `only_prompt` |
| Few-shot | `few_shot` |
| Grammar | `grammar` |
| Few-shot + Grammar | `few_shots_AND_grammar` |

Configured independently of the transformation branch. Ignored when the run mode
is Transformations Only.

### 3. Transformation Configuration

The transformation prompting strategy, from the same four. The card shows the
reading name and the run records the canonical id, as above. Ignored when the run
mode is Semantic Tests Only.

### 4. Experiment and Ablation

Refinement iterations (0–5), plus the RQ4 configuration: a named profile
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
one of its own. All twelve nodes stay connected to `Validate Config and Build
Run Queue` through `ai_languageModel`, which is how `selectedModel()` reads them
with `$(nodeName).params`.

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

On `SEMANTIC_EXECUTION_FAILED` the full pipeline diagnoses the source:

```text
transformation_defect -> transformation refinement
test_defect           -> test refinement
ambiguous             -> stop
```

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
   writes the raw response plus `generation-result.json` into the run.
3. **Stages** — `POST /runs/{run_id}/stages/{stage}`; n8n reads
   `{status, outcome_code, artifacts}` and routes on it.

`docs/n8n-python-contract.md` is authoritative for stage ids and
`outcome_code` values.

## Known limitations

* n8n form fields are static definitions in the workflow JSON, so the task lists
  are checked in rather than read from `benchmark/` at form-render time.
  `pipeline/tests/test_master_run_modes.py` asserts the form's options equal the
  task contracts on disk, so adding a contract fails the suite instead of
  silently becoming unselectable.
* Form pages are not conditionally shown: a tests-only run still walks past the
  Transformation Configuration screen, whose value is then ignored. Skipping a
  page would require branch-and-rejoin around a form node, which leaves the
  Validate node referencing an unexecuted node. Role requirements are enforced
  in validation instead.
* A card selects; it does not also advance the wizard. n8n forms submit native
  inputs only, so a control that both carried the value and moved to the next page
  would have to be a custom frontend behind a webhook. Each screen keeps its own
  continue button.
* Ablating a stage in the middle of a mode's pipeline still terminates
  `incomplete` with the stage-specific reason, as it did before run modes
  existed.
