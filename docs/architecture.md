# LLM4MTL architecture

> Status: authoritative active architecture. `measurement-spec.md` additionally
> governs the evaluation layer and wins where evaluation behaviour is concerned.

## Scope

This project builds a shared pipeline for generating, validating, executing, and
evaluating semantic tests for model transformations.

Transformation generation and the existing Java/Maven engines predate this
architecture:

- `engines/**` is frozen legacy code and is not refactored as part of the Python
  architecture;
- existing generated transformations are inputs to the semantic-test pipeline;
- adapters may invoke an engine through a narrow external-tool boundary, but
  engine internals do not define shared pipeline concepts;
- all engine execution happens in a materialized run-local copy.

The required transformation languages are ETL, ATL, QVT-O, and Reactions. All
four are registered through the same adapter boundary and have deterministic
rendering, parser integration, reference/generated-transformation execution,
and run-local evidence. There is no language fallback.

## Ownership

```text
n8n
  provider/model/strategy selection
  credentials and LLM calls
  LLM retries and routing
  observed token and latency facts
        │
        │ explicit schema-validated HTTP payloads
        ▼
stage_service
  transport and request validation only
        │
        ▼
shared Python stages
  deterministic extraction, rendering, validation, execution
  evidence collection, factual outcomes, artifact persistence
        │
        ├── run_store / experiment_store
        └── languages/<lang>/adapter
                    │
                    ▼
          run-local engine workspace
```

Python must not contain credentials, call an LLM, select a workflow route, or
return `next_action`. It reports facts as `status` plus `outcome_code`; n8n owns
the transition policy.

## Repository areas

- `schemas/` — persisted and cross-boundary JSON contracts.
- `engines/` — frozen parser/harness templates per language.
- `pipeline/` — Python package and tests. The importable package is
  `pipeline/src/llm4mtl/`.
- `benchmark/` — protected metamodels, references, fixtures, and task contracts.
- `prompt_assets/` — hand-authored prompt templates, grammar, and examples.
- `workflows/n8n/` — main workflow and provider/diagnosis subworkflows.
- `experiments/` — protected presets, variants, and matrices.
- `artifacts/work/` — generated, reproducible run output.
- `artifacts/published/` and `baseline/snapshot-*/` — frozen published inputs or
  prior results where present.

Generated output is never the source of truth for its generator. Fix renderers,
normalizers, schemas, or source inputs rather than hand-editing generated files.

## Python dependency direction

```text
domain
  ▲
  ├── semantic_tests
  │     ▲
  │     └── languages/<lang>   (implementations only; never languages/base.py)
  └── evaluation

external_tools / workspace / serialization
  ▲
  └── language adapters and stage use-cases

run_store / experiment_store
  ▲
  ├── experiment_runner
  └── stage_service
```

`domain/` is pure: no filesystem, subprocess, engine, or orchestration imports.
`languages/` depends on domain types and infrastructure boundaries. Shared
stages depend on `LanguageAdapter`, not on concrete languages. Evaluation must
derive results from stored facts and must not call language engines.

`languages/` sits *above* parts of `semantic_tests/`, not beside it: the
adapters reuse the shared Java emitter, suite helpers, Surefire reader, and
execution machinery rather than each carrying a copy. The direction is chosen,
not accidental — inverting it would make `semantic_tests/` import concrete
languages, which is the dependency the `LanguageAdapter` seam exists to
prevent. The seam itself stays clean: `languages/base.py` states the contract
using `domain/` types only, so everything a caller must understand to implement
a language is reachable without opening a stage.

## Established Python packages

- `artifact_schemas.py` — cached JSON Schema validators used by artifact stores.
- `domain/` — language-neutral artifact references, generated-suite identity,
  scenarios, observations, transformation outcomes, and the raw execution
  evidence an adapter returns beside them.
- `languages/` — `LanguageAdapter`, static registry, and concrete adapters.
- `task_contracts/` — deterministic structural contracts and enforcement.
- `prompt_assembly/` — exact task-input resolution and synchronization of the
  prompt/transformation/test n8n exports. It resolves files but never authors
  the natural-language task prompt. Inside `prompt_assembly/n8n_exports/`,
  `prompts.py` is the exact text every model receives and holds no n8n
  knowledge, `workflow_graph.py` is generic node/connection mechanics and holds
  no prompt knowledge, `synchronizers.py` states what each workflow is
  rewritten to do, and `sync.py` walks the files and owns `--write`.
- `semantic_tests/extraction/` — fenced artifact extraction, semantic-case
  normalization, shared-contract mapping, and deterministic renderer dispatch.
- `semantic_tests/validation.py` — shared artifact/technical/reference funnel.
- `semantic_tests/suite_execution.py` — one physical execution and its stored
  multi-fact observation.
- `semantic_tests/technical_validation/` and
  `semantic_tests/reference_validation/` — logical views over that observation.
- `transformation_execution/` — execution/reporting facade for generated
  transformations; candidate eligibility comes from the current run's
  reference-valid observation.
- `experiment_runner/` — local CLI orchestration and resume logic.
- `stage_service/` — FastAPI transport for n8n.
- `stage_recording.py` — how a stage attempt is recorded, for both entry points
  above: the started/finished events, the canonical payload, the evidence
  beside it, and the diagnosis assembler pinned to the attempt just written. A
  run directory reads the same whichever entry point produced it.
- `run_store/` — immutable run identity, append-only events, and atomic stage
  attempts.
- `experiment_store/` — immutable experiment identity and locked run membership.
  With `experiment_runner/matrix.py` and `evaluation/experiment_{aggregation,
  significance}.py` it forms the RQ4 ablation scaffold: written and tested, but
  deliberately not yet reachable from any entry point, because the matrix axes
  are fixed by the measurement spec and that is still settling. Runs today are
  created one at a time and never joined into an experiment.
- `provenance.py` — code, tool, schema, renderer, and protected-input identity.
- `paths.py` — the repository layout, and the one spelling of a recorded path:
  `repository_relative` keeps a path outside the repository absolute,
  `require_repository_relative` refuses it.
- `workspace/` — atomic materialization plus temporary injection/restore.
- `serialization/` — reading, writing, and content-hashing artifacts.
  `file_sha256`/`directory_sha256` live here because artifact identity is
  shared by provenance, the run store, prompt assembly, execution, and
  reporting alike, and belongs to none of them.
- `external_tools/` — structured subprocess boundaries.
- `evaluation/` — current aggregation plus frozen legacy analysis zones.
  `diagnosis_aggregation.py` and `experiment_*.py` are active;
  `evaluation/{atl,etl,qvto,reactions}/` is a behaviour-locked historical
  record of the analyses already run, kept reproducible rather than
  refactored. Its triplicated statistics modules, directory names containing
  spaces, and committed CSVs are intentional there and nowhere else; they are
  held in place by characterisation tests, not maintained.

Facade polishing and `_internal/` reorganisation remain frozen until the
measurement-driven boundaries settle.

## Language adapter boundary

`languages/base.py` defines a runtime-checkable `Protocol`. An adapter supplies:

- `language_id` and `renderer_version`;
- language runtime versions for provenance;
- deterministic suite rendering;
- reference transformation resolution;
- artifact validation;
- suite execution in a supplied `Workspace`;
- failure normalization into the shared outcome taxonomy;
- transformation syntax parsing into typed observations.

Registration is static in `languages/registry.py`. Missing required adapters fail
before a run writes partial results. There is no ETL fallback.

Prompt generation resolves
`reference → task_contract → exact task-specific metamodels`. Python owns this
deterministic and path-safe selection; n8n owns the LLM call. The LLM writes a
candidate natural-language task prompt under `artifacts/work/`. After review,
the frozen `prompt_assets/task_prompts/<lang>/<task>.txt` is the single prompt
read by both transformation generation and semantic-test generation. Neither
downstream stage reads prompt candidates or a model-specific alternative.

The semantic-test LLM also receives the exact task metamodel contents and the
selected few-shot/grammar strategy inputs, then writes its raw response as
`.md`. Python does not author the task prompt or replace an LLM stage; it
validates and renders the resulting declarative semantic artifacts after
extraction.

ATL and QVT-O render batch scenarios. Reactions renders the shared declarative
change vocabulary into Vitruv operations; it never accepts generated Java or
Xtend change code. ATL, QVT-O, and Reactions also write deterministic EMF XMI
snapshots beneath the supplied workspace observation directory. These raw
snapshots are execution evidence; semantic equivalence remains owned by the
future shared comparator.

The frozen Reactions harness contains an unused dependency on an unpublished
SDQ demo artifact. Its adapter removes that dependency only from the
materialized run-local POM. The engine template is not edited. The frozen
standalone Reactions parser also reports unresolved generated metamodel types
as semantic-link diagnostics; the adapter distinguishes those known diagnostics
from grammar errors, while the run-local Maven compilation remains the
semantic-link authority.

The active adapter is intentionally narrower than the eventual measurement
subsystem. Mutation, instrumentation, and semantic snapshot comparison are
separate capabilities with different lifecycles; they must not turn
`LanguageAdapter` into a generic plugin or God object.

See `adding-language.md` for the implementation template and contract tests.

## Run identity and storage

A run fixes exactly one value for each applicable identity axis:

```text
language
task
transformation model and strategy
test-generation model and strategy
seed
pipeline variant
```

An axis may be `null` in the manifest only when no stage in that run consumes
it. `null` never means “select all”. Multi-task/model/strategy experiments must
expand through a matrix before run creation.

Stage requests cannot repeat or override identity. They carry only
attempt-specific parameters such as `suite_id` and `verbose`.

```text
artifacts/work/runs/<run-id>/
├── manifest.json
├── events.jsonl
├── config.resolved.yaml
├── summary.json
├── runner.log
├── observations/
├── workspaces/
├── responses/
│   ├── semantic-test-generation/iteration-NNN/
│   ├── transformation-generation/iteration-NNN/
│   └── source-diagnosis/execution-attempt-NNN/
└── stages/
    └── <contract-stage>/
        └── attempts/
            └── attempt-NNN/
                ├── result.json
                └── evidence.json
```

A run directory holds the state of one run: its workspaces, its logs, and the
evidence its stages recorded. Results other work consumes do not live there,
because handing a consumer a run means telling them which parts to ignore. The
failure diagnosis is such a result — refinement routes on it, reporting counts
it, analysis reads it across runs — so it is stored in its own area, keyed by
the run that produced it and carrying no run state:

```text
artifacts/work/diagnoses/<run-id>/attempt-NNN/diagnosis.json
```

The run keeps no copy and no pointer; `events.jsonl` still records that a
`diagnosis_recorded` event happened, and the run id is what links the two.

Invariants:

- `run_id`, experiment id, and suite id are opaque one-component identifiers;
- `manifest.json` is write-once;
- `events.jsonl` is append-only and locked;
- attempt directories are claimed atomically;
- `result.json` is the canonical `stage-result` payload;
- internal selections, errors, and debug detail belong in `evidence.json`;
- the latest result is derived from the highest recorded attempt—there is no
  mutable `latest.json`;
- stored manifests, events, stage results, diagnoses, experiment indices, and
  suite-execution observations are validated on write and read;
- run-store schemas are version `2.0`; generated v1 work artifacts are
  regenerated, never rewritten as if they had originally used v2.

Provenance in the immutable manifest records the git revision and dirty state,
schema versions, renderer version, runtime tool versions, and hashes of the
reference transformation, task contract, exact task metamodels, and shared
frozen task prompt.

## Workspace and candidate immutability

An engine directory is a read-only template. Before an executable stage, Python
atomically copies it under:

```text
runs/<run-id>/workspaces/<language>/
```

Concurrent calls share only the completed run-local materialization and
serialize injection into that copy. The template never receives generated
files, locks, Maven output, or parser results.

Extracted candidate suites are immutable. Reusing a `suite_id` cannot overwrite
the existing directory, even through the compatibility `--overwrite` flag.
Choose a new suite id for a new artifact.

Reference validation records a decision; it does not copy a candidate into
`validated/`. CSV output is a derived human report only and cannot gate another
stage.

## Validation funnel

The funnel keeps three questions separate:

```text
generated
  → artifact valid?
  → technically executable?
  → reference-valid oracle?
```

The LLM supplies semantic cases and model artifacts. Python discards all
LLM-authored Java. Missing or malformed `semantic_cases.json` creates an
artifact-invalid candidate and never reaches Maven.

Technical and reference validation use one physical execution against the
trusted reference transformation. That execution records independent facts:

```text
compiled
tests_discovered
models_loaded
engine_started
assertions_evaluated
assertions_passed
timed_out
failure_stage
```

An assertion failure is technically executable and reference-invalid. A compile
failure, missing test, model-loading failure, or unknown runtime error is not an
oracle disagreement.

The observation is keyed by language/task/model/strategy/suite and by hashes of
the exact suite and reference transformation. A later stage reuses it only when
the full identity and hashes match and the observation lives under the current
run.

## Stage contract

Persisted stage results use `schemas/stage-result.schema.json` version `2.0`:

```text
schema_version
stage
status
outcome_code
counts
artifacts
attempt
```

Stage status is one of `passed`, `failed`, `skipped`, or
`infrastructure_error`. `skipped` is never projected onto `passed`; a run with a
fully skipped stage is `incomplete`. Infrastructure failure is orthogonal to
domain failure and routes to retry/stop in n8n.

See `n8n-python-contract.md` and `runner-api.md`.

## Measurement layer

`measurement-spec.md` is authoritative. The controlled BA campaign uses a
standalone `evaluation/` layer over immutable production artifacts. Fixed
held-out suites, deterministic mutants, qualification/baseline/generated suite
roles, static EClass coverage, and derived CSVs belong there; they do not add
production nodes, endpoints, ledgers, telemetry, or runtime instrumentation.

Language adapters are reused only as the existing parser/execution boundary and
all evaluator workspaces are temporary. Run directories remain read-only inputs.
