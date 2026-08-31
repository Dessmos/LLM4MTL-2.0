# Data flow

> Status: active description of the implemented four-language semantic-test
> pipeline. Mutation evaluation and cost ingest are identified separately as
> target work.

## Control and data planes

n8n is the control plane: it selects providers/models/strategies, invokes LLMs,
applies retry/routing policy, and calls the Python stage service.

Python is the deterministic data plane: it validates boundaries, renders
executable artifacts, invokes local tools, records observations, and returns
factual outcomes.

```text
n8n
  │ POST /runs (complete immutable identity)
  ▼
run_store
  │ manifest.json + run_created event
  ▼
n8n
  │ POST /runs/<run-id>/stages/<stage>
  ▼
shared Python stage → LanguageAdapter → run-local workspace
  │
  ├── canonical result.json
  ├── internal evidence.json
  └── append-only events.jsonl
```

Stage requests cannot redefine language, task, models, strategies, seed, or
variant. Those selections are reconstructed from the manifest.

## Shared task-prompt generation and LLM input

Prompt generation and the two downstream generators are separate LLM calls
owned by n8n:

```text
reference transformation
  → matching task_contract
  → exact metamodel files named by that contract
  + language grammar
  → prompt-generation LLM
  → artifacts/work/task_prompt_candidates/<lang>/<model>/<task>.txt
  → human review / checked-in freeze
  → prompt_assets/task_prompts/<lang>/<task>.txt
  ├─→ transformation-generation LLM
  └─→ semantic-test-generation LLM
       + the same exact task metamodels
       + prompt_assets/tests/contract/<lang>/semantic_cases_contract.txt
       + selected few-shot/grammar strategy inputs
       → artifacts/work/runs/<run-id>/responses/semantic-test-generation/
         iteration-<NNN>/prompt.md
       → artifacts/work/runs/<run-id>/responses/semantic-test-generation/
         iteration-<NNN>/<task>.md
```

The output contract is delivered on every strategy, not only on `few_shot`: it
is what the extractor enforces, so a variant that omits it asks for a
structured artifact without ever stating its shape, and the strategy axis would
compare "with examples" against "without a contract". The assembled prompt is
archived beside the run-scoped response it produced, because a response that
violates the contract is otherwise indistinguishable from a prompt that never
carried it.

The first LLM reconstructs only a concise natural-language task request; Python
does not generate that text. Python deterministically validates the task
contract and resolves the reference plus its exact metamodel paths. The raw
task-contract JSON is not supplied to the LLM.

Resolution is identical for every language and fails closed on any of: an
unknown task name, a path escaping the protected benchmark tree, a contract
whose `language` disagrees with the request, or a contract whose `sourceHash`
no longer matches the reference bytes. That last check is what keeps an edited
reference from being described by a contract built for an older version of it. Candidate prompts remain
untrusted output and are never consumed directly by evaluation. The reviewed
file under `prompt_assets/task_prompts/` is the single task prompt used by both
downstream generators.

The semantic-test LLM must produce declarative `semantic_cases.json` and input
model files, never Java/JUnit or transformation code. Its `.md` response is
untrusted generated output.

## Semantic-test generation and extraction

The LLM response is an untrusted input. It may supply:

- `semantic_cases.json`;
- source/input model files;
- other declarative model resources.

It does not supply trusted Java infrastructure.

```text
raw response Markdown
  → fenced artifact extraction
  → discard every LLM-authored .java file
  → normalize semantic_cases.json
  → validate the semantic-case schema
  → enforce the task contract
  → map into the shared scenario model
  → language adapter renders deterministic harness
  → immutable candidate suite + artifact-validation metadata
```

If `semantic_cases.json` is missing or malformed, or if task/domain validation
fails, extraction still records an artifact-invalid candidate for funnel
accounting, but emits no executable Java and never reaches Maven.

Candidate layout:

```text
artifacts/work/test_generation/generated_tests/<lang>/
└── <task>/
    └── candidates/
        └── <test-model>/
            └── <test-strategy>/
                └── <suite-id>/
                    ├── semantic_cases.json
                    ├── metadata.json
                    ├── models/
                    └── Generated...Test.java
```

A candidate directory is immutable. A second artifact needs a new `suite-id`;
the compatibility `--overwrite` flag cannot replace scientific evidence.

## Syntax validation

The transformation parser is selected through `LanguageAdapter`:

```text
selected generated transformations
  → adapter.parse_transformations(...)
  → existing language parser as external tool
  → typed ParseObservation per transformation
  → run-local parser evidence
```

For ETL, the frozen parser still emits a compatibility CSV, but the adapter
redirects it beneath the current run's observation directory. It is evidence,
not a gate, and nothing is written to `engines/etl/parser/results`.

Every parser executes from a run-local materialization. ATL and QVT-O normalize
their parser markers into typed observations. The frozen Reactions parser lacks
the harness-generated metamodel classes and therefore reports a small known set
of unresolved-link diagnostics for otherwise valid references; those
diagnostics do not become grammar failures. Actual semantic linking is still
checked by compilation in the run-local Reactions harness.

## Technical and reference validation

Technical executability and oracle validity are logical views over one physical
execution against the trusted reference transformation:

```text
immutable candidate
  → artifact validation
  → current run's materialized harness
  → inject candidate + trusted reference temporarily
  → mvn clean test
  → Surefire/console classification
  → SuiteExecutionObservation
  → restore injected files
```

The observation records:

```text
compiled
tests_discovered
models_loaded
engine_started
assertions_evaluated
assertions_passed
timed_out
maven_exit_code
failure_stage
error_summary
```

The technical view asks whether an assertion verdict was reached. The reference
view asks whether the assertions passed. Therefore:

```text
assertion failure
  → technically executable = true
  → reference valid = false
```

The record is stored under the current run:

```text
runs/<run-id>/observations/
└── <task>/<model>/<strategy>/<suite-id>/suite_execution.json
```

It contains typed references and hashes for both the suite and reference
transformation. A technical stage and a reference stage reuse the same record
only when those identities and hashes match. Per-suite locks prevent concurrent
calls from executing the same mutable run-local harness twice.

There is no global CSV gate and no physical promotion into `validated/`.

## Execution on generated transformations

The execution stage selects:

- transformations that passed syntax validation in the current stage flow;
- immutable candidate suites whose current-run reference observation is
  technically executable and reference-valid.

```text
current-run reference-valid candidate
  × parsable generated transformation
  → run-local harness execution
  → typed execution observation / normalized failure
  → stage counts and evidence
```

The standalone `transformation_execution` CLI follows the same eligibility rule:
it requires `--observations-root` and does not discover historical
`validated/` copies.

All four languages render post-execution EMF snapshots of the actual target
models. A snapshot's identity is transformation + suite + test case + model
slot, and the path states all four:

```text
runs/<run-id>/observations/<task>/<llm>/<strategy>/<suite-id>/
    suite_execution.json
    execution_evidence/
    snapshots/<test-case>/<model-slot>.xmi      reference execution

runs/<run-id>/observations/generated_transformations/<sha256>/
    <task>/<llm>/<strategy>/<suite-id>/
        snapshots/<test-case>/<model-slot>.xmi  generated-transformation execution
```

Scoping to the suite is not cosmetic. One directory per transformation let two
suites with the same case name overwrite each other's actual output, and a
diagnosis assembled from the survivor would cite a model that the failing
execution never produced.

Each execution also writes a schema-validated `suite_execution.json` beneath
the corresponding observation root. At this stage the JUnit assertions, not
byte comparison of snapshots, determine suite success.

## Four-language task inputs

The static registry contains exactly:

```text
etl, atl, qvto, reactions
```

For each language, tasks are data under `benchmark/tasks/<lang>/` and matrices
under `experiments/matrices/`. Adding a task does not change shared stage code.
The language's prompt-generation workflow identifies a reference task. The
stage service follows that reference to its task contract and rejects missing,
escaping, or stale paths instead of falling back to a language-wide metamodel
glob. Few-shot and grammar strategy inputs for downstream LLMs remain explicit
in n8n.

The repository includes opt-in real-engine walking skeletons for one
representative task per language. They traverse schema/contract validation,
rendering, parsing, reference execution, generated-transformation execution,
snapshot/evidence storage, and workspace cleanup.

## Run completion

Each stage call creates:

```text
stages/<stage>/attempts/attempt-NNN/
├── result.json      # canonical schema-validated stage contract
└── evidence.json    # internal selections and diagnostics
```

Attempt numbers and immutable manifests are claimed atomically. The latest stage
result is derived from recorded attempts. Events are appended under a file lock.

Run status is derived from stage facts:

- infrastructure error → `failed`;
- domain failure → `completed_with_failures`;
- fully skipped stage → `incomplete`;
- otherwise → `completed`.

## Diagnosis

Evidence assembly is triggered by the execution stage and by nothing earlier. A
generated test reaches this point only by having passed on the reference
transformation first, so the failure being diagnosed is always a failure of the
generated transformation, never an unproven oracle:

```text
execution attempt recorded
  → counts.failed > 0
  → for each pair with assertions_passed = false
      → archived Surefire <failure>/<error> entries
        ├─ named a test method
        │    → method name → exactly one semantic case
        │    → failure message → exactly one assertion (assertion failures only)
        │    → one immutable per-case report per recorded failure
        └─ named none
             → one immutable pair-level report for the whole execution
  → diagnosis/execution/attempt-NNN/index.json
```

Preparation reads only the immutable attempt that was just written. It never
changes the stage result, the run status, or the events timeline, and a failure
to assemble evidence is recorded in the index rather than failing the stage.
The same assembly is available as `llm4mtl diagnosis prepare --run <run-id>`.

The mapping back from a Surefire method to a semantic case is the renderer's own
name function applied to every case; the mapping from a failure message to an
assertion is the renderer's own message format. A method or message that could
have come from more than one case or assertion is refused, with the reason
recorded, rather than attributed to the first candidate.

Before an LLM diagnosis, Python can also assemble one such bundle directly from
the immutable run facts:

```text
manifest + syntax attempt + execution attempt
  + semantic_cases.json + input/actual models + comparator difference
  + task prompt + exact metamodels + reference result + Surefire evidence
  → one immutable per-assertion failure report
```

The local orchestration command is:

```text
llm4mtl diagnosis report --request <request.json> --output <report.json>
```

It emits a Source Diagnosis bundle only when four conditions hold, in the order
the pipeline establishes them:

```text
the generated transformation is syntactically valid
AND the suite passed on the reference transformation
AND a real failure of the pairing was observed on the generated one
AND enough execution evidence survived to say what happened
```

A JUnit assertion failure is not one of them. A validated test that *throws* on
a generated transformation has failed against it just as much, and that is
usually what a broken transformation produces; the report then names no
assertion (`assertion_id: null`), carries the exception and stack trace as its
evidence, and leaves `expected`/`actual` null. Excluded instead is a timeout or
an infrastructure failure, because neither is evidence about the pairing.

When the failure *is* an assertion failure, the selected `test_case_id` and
`assertion_id` must match the Surefire failure.

Three independent things can carry that observed result, and the report names
which of them it has:

```text
actual target-model snapshots        written by the harness, per test case
expected/actual from JUnit           read verbatim out of the archived failure message
structured comparator difference     not produced yet; optional
```

The `expected`/`actual` pair is extracted only from the exact
`expected: <X> but was: <Y>` shape; any other message records both as `null`
beside the raw message. The structured actual-vs-expected difference remains an
observed comparator input, and the assembler never infers it from an error
string. When none of the three is present the report is still written, with
`source_diagnosis.reason = no_observed_actual_result`.

This report command is deterministic post-execution processing rather than a
new contract stage. It does not rewrite the execution attempt, call an LLM,
classify the source, or return a workflow route.

When n8n decides that the prepared semantic failure needs LLM diagnosis, it
sends the normalized diagnosis result to:

```text
POST /runs/<run-id>/diagnoses
```

Python validates it against `diagnosis.schema.json`, stores it as an immutable
response attempt, and appends `diagnosis_recorded`. Provider selection and the
diagnosis LLM call remain in n8n.

## Offline measurement flow

The controlled BA campaign evaluates completed runs outside n8n:

```text
selected run ids + strict experiment_config preflight
  → fixed held-out suites × stored transformation iterations
  → deterministic mutants × qualification/baseline/generated suites
  → static EClass analysis of stored generated inputs
  → derived observation CSVs
  → metric CSV
```

These procedures reuse immutable artifacts and temporary engine workspaces. They
do not add production telemetry, endpoints, ledgers, or n8n nodes. See
`measurement-spec.md` for the frozen populations and denominators.
