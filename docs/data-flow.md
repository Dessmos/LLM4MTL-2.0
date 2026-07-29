# Data flow

> Status: active description of the implemented ETL semantic-test vertical
> slice. Mutation evaluation, cost ingest, and the remaining language adapters
> are identified separately as target work.

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

When n8n decides that semantic failure needs LLM diagnosis, it sends the
normalized diagnosis result to:

```text
POST /runs/<run-id>/diagnoses
```

Python validates it against `diagnosis.schema.json`, stores it as an immutable
response attempt, and appends `diagnosis_recorded`. Provider selection and the
diagnosis LLM call remain in n8n.

## Target measurement flow

The following measurement stages are specified but not yet implemented:

```text
versioned per-language mutation operators
  → fixed qualification corpus Q
  → shared semantic outcome comparison
  → frozen qualified mutant catalog M_Q
  → reference-valid suite × M_Q
  → confirmed kills / coherence audit
  → run metrics
  → experiment aggregation and significance
```

Typed LLM-call telemetry will also enter the run journal once its ingest schema
and endpoint are implemented. `measurement-spec.md` is authoritative for these
future stages.
