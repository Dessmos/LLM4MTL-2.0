# Experiment Runner: Complete CLI Contract

`Experiment_Runner` is the single public entry point for every experiment stage
except n8n generation. Run all commands from the repository root:

```bash
python3 -m Experiment_Runner <command> <action> [options]
```

The five available operations are:

```bash
python3 -m Experiment_Runner tests extract [options]
python3 -m Experiment_Runner tests validate [options]
python3 -m Experiment_Runner transformations parse [options]
python3 -m Experiment_Runner transformations validate [options]
python3 -m Experiment_Runner pipeline run [options]
```

## Common parameters

The following parameters are available for all five operations. For
`pipeline run --config`, some work only as execution overrides; the restrictions
are listed in that command's section.

| Parameter | Value | Description |
| --- | --- | --- |
| `--language` | `etl` | Selects the transformation language. Only ETL is currently supported. |
| `--task TASK` | for example, `Tree2Graph` | Selects a task. Can be repeated for multiple tasks. |
| `--all-tasks` | flag | Selects all discovered tasks. Mutually exclusive with `--task`. |
| `--dry-run` | flag | Performs discovery and shows the plan without creating runtime files or running Maven. |
| `--run-id ID` | string | Sets the run identifier and metadata directory. An ID is generated automatically when omitted. |
| `--resume` | flag | Resumes an existing run and skips successful stages only when the configuration and input hashes match. |
| `--force` | flag | Ignores saved successful results and reruns selected stages. It also permits rerunning an existing `run-id`. |
| `--output-format` | `text` or `json` | Selects human-readable or machine-readable output. Defaults to `text`. |
| `--verbose` | flag | Shows low-level tool commands and their extended output. |
| `--keep-workspace` | flag | Preserves a separate Maven project copy in the run directory. Useful for debugging validation. |
| `--fail-fast` | flag | Stops a multi-stage run after the first stage error or domain failure. |

At least one selection source is required: `--task`, `--all-tasks`, or a direct
response, suite, or transformation path. `--task` and `--all-tasks` are mutually
exclusive.

Allowed models:

```text
gpt-5
claude-sonnet-4
gemini-2-5-pro
```

Allowed strategies:

```text
only_prompt
few_shot
grammar
few_shots_AND_grammar
```

When a model or strategy filter is omitted, all allowed values found for the
selected tasks are used.

## 1. Extract generated test suites

```bash
python3 -m Experiment_Runner tests extract [options]
```

This command locates Markdown responses, extracts their test files, and creates
candidate suites under `Test_Generation/generated_tests/etl`.

### `tests extract` parameters

| Parameter | Description |
| --- | --- |
| `--language etl` | Selects ETL. |
| `--task TASK` | Extracts responses for the specified task; can be repeated. |
| `--all-tasks` | Extracts responses for all discovered tasks. |
| `--test-model MODEL` | Filters by the model that generated the tests; can be repeated. |
| `--test-strategy STRATEGY` | Filters by prompting strategy; can be repeated. |
| `--response PATH` | Selects a specific Markdown response; can be repeated. The model, strategy, and task are inferred from the standard response path. |
| `--suite-id ID` | Assigns an explicit suite identifier, for example `suite_001`. Allowed only with one `--response`. |
| `--overwrite` | Allows replacing an existing directory with the selected `suite-id`. |
| `--no-overwrite` | Explicitly prevents replacing an existing directory. This safe behavior is also the default. |
| `--dry-run` | Shows discovered responses and the planned result without writing files. |
| `--run-id ID` | Sets the run ID. |
| `--resume` | Uses the previous successful result when the hashes match. |
| `--force` | Reruns extraction regardless of the saved stage result. |
| `--output-format text\|json` | Selects the output format. |
| `--verbose` | Shows extended extraction-tool output. |
| `--keep-workspace` | Accepted by the common CLI; extraction does not require a separate Maven workspace. |
| `--fail-fast` | Stops on an extraction error. This single-stage command has no later stage to skip. |

Without `--response`, the command searches for files using this layout:

```text
Test_Generation/Workflows/n8n-docker/mtl_snippets/ETL_test_generation/
responses/<test-model>/<test-strategy>/<task>.md
```

The result is stored using this layout:

```text
Test_Generation/generated_tests/etl/
<task>/candidates/<test-model>/<test-strategy>/<suite-id>/
```

When `--suite-id` is omitted, the next free ID is created. A regular bulk
extraction therefore does not overwrite previous suites. To replace a specific
suite, pass both `--suite-id` and `--overwrite`.

Extract all responses for one task:

```bash
python3 -m Experiment_Runner tests extract \
  --language etl \
  --task Tree2Graph
```

Extract only GPT-5 `few_shot` responses:

```bash
python3 -m Experiment_Runner tests extract \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot
```

Extract one response into a specific suite:

```bash
python3 -m Experiment_Runner tests extract \
  --language etl \
  --response Test_Generation/Workflows/n8n-docker/mtl_snippets/ETL_test_generation/responses/gpt-5/few_shot/Tree2Graph.md \
  --suite-id suite_001
```

Overwrite this suite:

```bash
python3 -m Experiment_Runner tests extract \
  --language etl \
  --response Test_Generation/Workflows/n8n-docker/mtl_snippets/ETL_test_generation/responses/gpt-5/few_shot/Tree2Graph.md \
  --suite-id suite_001 \
  --overwrite
```

Inspect discovery without writing files:

```bash
python3 -m Experiment_Runner tests extract \
  --language etl \
  --task Tree2Graph \
  --dry-run
```

Constraints:

- `--suite-id` requires exactly one `--response`;
- `--all-tasks` cannot be combined with `--response`;
- `--task` cannot be combined with `--all-tasks`;
- `--overwrite` and `--no-overwrite` are mutually exclusive.

## 2. Validate generated test suites

```bash
python3 -m Experiment_Runner tests validate [options]
```

This command runs technical validation, reference validation, or both stages.
The default is `--stage all`: technical first, then reference validation.

### `tests validate` parameters

| Parameter | Description |
| --- | --- |
| `--language etl` | Selects ETL. |
| `--stage all` | Runs technical and then reference validation. This is the default. |
| `--stage technical` | Runs only technical checks for suite structure, compilation, and execution. |
| `--stage reference` | Runs only reference validation. Suites without a successful technical result are skipped. |
| `--task TASK` | Selects candidates for a task; can be repeated. |
| `--all-tasks` | Selects candidates for all tasks. |
| `--test-model MODEL` | Filters suites by test-generation model; can be repeated. |
| `--test-strategy STRATEGY` | Filters suites by test-generation strategy; can be repeated. |
| `--suite-id ID` | Selects one suite by ID. Without a direct `--suite`, exactly one `--task`, `--test-model`, and `--test-strategy` are required. |
| `--suite PATH` | Supplies a direct candidate-suite path; an advanced/debug override that can be repeated. |
| `--dry-run` | Shows selected candidate suites without running Maven. |
| `--run-id ID` | Sets the run ID. |
| `--resume` | Skips an already successful stage when the hashes match. |
| `--force` | Repeats validation regardless of the saved stage result. |
| `--output-format text\|json` | Selects the output format. |
| `--verbose` | Shows extended validation-tool and Maven output. |
| `--keep-workspace` | Runs validation in a preserved copy of `ETL_Test` inside the run directory. |
| `--fail-fast` | With `--stage all`, does not start the next stage after the first error or failed result. |

Validate one task completely:

```bash
python3 -m Experiment_Runner tests validate \
  --language etl \
  --task Tree2Graph
```

Technical validation only:

```bash
python3 -m Experiment_Runner tests validate \
  --language etl \
  --task Tree2Graph \
  --stage technical
```

Reference validation only:

```bash
python3 -m Experiment_Runner tests validate \
  --language etl \
  --task Tree2Graph \
  --stage reference
```

Validate one suite by identifiers:

```bash
python3 -m Experiment_Runner tests validate \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --suite-id suite_001
```

Validate one candidate suite by direct path:

```bash
python3 -m Experiment_Runner tests validate \
  --language etl \
  --suite Test_Generation/generated_tests/etl/Tree2Graph/candidates/gpt-5/few_shot/suite_001
```

Atomic suite policy:

```text
all tests pass reference    -> VALIDATED
at least one test fails     -> REFERENCE_INVALID
Maven/pipeline malfunction  -> INFRASTRUCTURE_ERROR
```

Successful suites are copied to:

```text
Test_Generation/generated_tests/etl/
<task>/validated/<test-model>/<test-strategy>/<suite-id>/
```

Reference-invalid suites are copied in full to:

```text
Test_Generation/generated_tests/etl/
<task>/invalid/<test-model>/<test-strategy>/<suite-id>/
```

Infrastructure errors are not classified as LLM errors and are not copied to
`invalid`. With `--stage reference`, the absence of successful technical
validation results in `SKIPPED_MISSING_TECHNICAL_VALIDATION`.

## 3. Syntax-check generated transformations

```bash
python3 -m Experiment_Runner transformations parse [options]
```

This command checks selected `.etl` files with the existing ETL parser before
semantic tests are run.

### `transformations parse` parameters

| Parameter | Description |
| --- | --- |
| `--language etl` | Selects ETL. |
| `--task TASK` | Selects transformations for a task; can be repeated. |
| `--all-tasks` | Selects transformations for all tasks. |
| `--transformation-model MODEL` | Filters transformations by generation model; can be repeated. |
| `--transformation-strategy STRATEGY` | Filters transformations by prompting strategy; can be repeated. |
| `--transformation PATH` | Supplies a direct `.etl` path; can be repeated. Direct paths replace discovery filters. |
| `--dry-run` | Shows selected transformations without running the parser. |
| `--run-id ID` | Sets the run ID. |
| `--resume` | Uses a successful parser result when the hashes match. |
| `--force` | Reruns the parser regardless of the saved result. |
| `--output-format text\|json` | Selects the output format. |
| `--verbose` | Shows extended parser-tool output. |
| `--keep-workspace` | Accepted by the common CLI; the parser does not require a separate Maven workspace. |
| `--fail-fast` | Stops on a parser-stage error. This single-stage command has no later stage to reorder. |

By default, transformations are discovered in the canonical store:

```text
Workflows/n8n-docker/mtl_snippets/ETL_language/
responses/<transformation-model>/<transformation-strategy>/<task>.etl
```

Check one model and strategy:

```bash
python3 -m Experiment_Runner transformations parse \
  --language etl \
  --task Tree2Graph \
  --transformation-model claude-sonnet-4 \
  --transformation-strategy grammar
```

Check one file directly:

```bash
python3 -m Experiment_Runner transformations parse \
  --language etl \
  --transformation Workflows/n8n-docker/mtl_snippets/ETL_language/responses/claude-sonnet-4/grammar/Tree2Graph.etl
```

Parser CSV results are stored in:

```text
ETL_Parser/results/etl/generated_transformation_syntax.csv
```

## 4. Run validated tests on generated transformations

```bash
python3 -m Experiment_Runner transformations validate [options]
```

This command builds pairs only between validated suites and transformations for
the same task, runs the tests, and stores results and diagnostic artifacts.

### `transformations validate` parameters

| Parameter | Description |
| --- | --- |
| `--language etl` | Selects ETL. |
| `--task TASK` | Selects a task; can be repeated. |
| `--all-tasks` | Selects all tasks for which both sides of a pair are found. |
| `--test-model MODEL` | Selects the model that generated the tests; can be repeated. |
| `--test-strategy STRATEGY` | Selects the test-generation strategy; can be repeated. |
| `--suite-id ID` | Selects a specific validated suite. Without a direct `--suite`, exactly one `--task`, `--test-model`, and `--test-strategy` are required. |
| `--suite PATH` | Supplies a direct validated-suite path; an advanced/debug override that can be repeated. |
| `--transformation-model MODEL` | Selects the model that generated the transformation; can be repeated. |
| `--transformation-strategy STRATEGY` | Selects the transformation-generation strategy; can be repeated. |
| `--transformation PATH` | Supplies a direct `.etl` path; can be repeated. |
| `--dry-run` | Shows selected suites, transformations, and all execution pairs without running Maven. |
| `--run-id ID` | Sets the run ID. |
| `--resume` | Uses a successful semantic result when the hashes match. |
| `--force` | Reruns semantic validation regardless of the saved result. |
| `--output-format text\|json` | Selects the output format. |
| `--verbose` | Shows extended validation-tool and Maven output. |
| `--keep-workspace` | Runs checks in a preserved copy of `ETL_Test` inside the run directory. |
| `--fail-fast` | Stops on a semantic-stage error. The low-level runner still processes the selected matrix according to its contract. |

GPT-5 tests against all Claude transformations for `Tree2Graph`:

```bash
python3 -m Experiment_Runner transformations validate \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --transformation-model claude-sonnet-4
```

One suite against transformations from a specific strategy:

```bash
python3 -m Experiment_Runner transformations validate \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --suite-id suite_001 \
  --transformation-model claude-sonnet-4 \
  --transformation-strategy grammar
```

One suite and one `.etl` file by direct paths:

```bash
python3 -m Experiment_Runner transformations validate \
  --language etl \
  --suite Test_Generation/generated_tests/etl/Tree2Graph/validated/gpt-5/few_shot/suite_001 \
  --transformation Workflows/n8n-docker/mtl_snippets/ETL_language/responses/claude-sonnet-4/grammar/Tree2Graph.etl
```

Show the execution matrix without running it:

```bash
python3 -m Experiment_Runner transformations validate \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --transformation-model claude-sonnet-4 \
  --dry-run
```

Without model/strategy filters, the command for a specific task means:

```text
all validated suites for that task
×
all generated transformations for that task
```

Detailed results are owned by `Transformation_Validation`:

```text
Transformation_Validation/results/etl/transformation_validation.csv
Transformation_Validation/artifacts/etl/<task>/<test-suite>/<transformation>/
```

Artifacts contain the input suite, transformation, Maven output, and metadata.
This makes it possible to provide the failed test and the tested transformation
to an LLM together.

## 5. Run the complete pipeline with one command

```bash
python3 -m Experiment_Runner pipeline run [options]
```

Stage order:

```text
extract
  -> technical
  -> reference
  -> parsing
  -> semantic
```

Only transformations that pass `parsing` are passed to `semantic`.

### `pipeline run` parameters

| Parameter | Description |
| --- | --- |
| `--config PATH` | Loads a reproducible experiment from YAML or JSON. |
| `--language etl` | Selects ETL when running without a config. |
| `--task TASK` | Selects a task when running without a config; can be repeated. |
| `--all-tasks` | Selects all tasks when running without a config. |
| `--test-model MODEL` | Filters responses/candidate/validated suites by test model; can be repeated. |
| `--test-strategy STRATEGY` | Filters test suites by strategy; can be repeated. |
| `--suite-id ID` | Selects one suite. Exactly one `--task`, `--test-model`, and `--test-strategy` are required. |
| `--transformation-model MODEL` | Filters generated transformations by model; can be repeated. |
| `--transformation-strategy STRATEGY` | Filters generated transformations by strategy; can be repeated. |
| `--transformation PATH` | Supplies one `.etl` path directly; can be repeated. |
| `--start-stage STAGE` | Starts at `extract`, `technical`, `reference`, `parsing`, or `semantic`. Defaults to `extract`. |
| `--stop-after STAGE` | Stops after the specified stage. Defaults to `semantic`. |
| `--dry-run` | Shows the plan for all selected stages without writing runtime files or running Maven. |
| `--run-id ID` | Sets the ID for the linked experiment run. |
| `--resume` | Resumes the run and skips successful unchanged stages. If only `--run-id` and `--resume` are supplied, selectors are loaded from the existing run's resolved config. |
| `--force` | Reruns stages, ignoring resume eligibility. |
| `--output-format text\|json` | Selects the summary format; JSON is also intended for UI and multi-agent clients. |
| `--verbose` | Shows extended logs from low-level components. |
| `--keep-workspace` | Preserves the Maven workspace at `Experiment_Runner/runs/<run-id>/workspace/ETL_Test`. |
| `--fail-fast` | Stops the pipeline after the first infrastructure error or domain failure. |

Run one complete combination:

```bash
python3 -m Experiment_Runner pipeline run \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --transformation-model claude-sonnet-4 \
  --transformation-strategy grammar
```

Run only test extraction and validation:

```bash
python3 -m Experiment_Runner pipeline run \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --stop-after reference
```

Start with already validated suites:

```bash
python3 -m Experiment_Runner pipeline run \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --suite-id suite_001 \
  --transformation-model claude-sonnet-4 \
  --start-stage semantic
```

Resume an existing run without repeating selectors:

```bash
python3 -m Experiment_Runner pipeline run \
  --run-id etl-tree2graph-001 \
  --resume
```

Full dry run:

```bash
python3 -m Experiment_Runner pipeline run \
  --language etl \
  --task Tree2Graph \
  --test-model gpt-5 \
  --test-strategy few_shot \
  --transformation-model claude-sonnet-4 \
  --dry-run
```

## Run from a YAML/JSON configuration

For reproducible experiments, use the files in `experiments/etl`:

```bash
python3 -m Experiment_Runner pipeline run \
  --config experiments/etl/gpt_tests_vs_claude.yaml
```

Example structure:

```yaml
schema_version: 1
language: etl

tasks:
  - Tree2Graph

test_suites:
  models:
    - gpt-5
  strategies:
    - few_shot
  extraction:
    enabled: true
    overwrite: false
  validation:
    technical: true
    reference: true
    atomic_suite_policy: true

transformations:
  models:
    - claude-sonnet-4
  strategies:
    - only_prompt
    - grammar
    - few_shot
    - few_shots_AND_grammar
  parse: true
  semantic_validation: true

execution:
  start_stage: extract
  stop_after: semantic
  resume: true
  fail_fast: false
  keep_workspace: false
  output_format: text
```

`atomic_suite_policy: true` records the experiment's protocol decision. This
policy is currently always enabled and cannot be disabled by setting it to
`false`. `schema_version` is intended to version the experiment-config format.

When `--config` is used, the following CLI selectors are forbidden:

```text
--language
--task
--all-tasks
--test-model
--test-strategy
--suite-id
--transformation-model
--transformation-strategy
--transformation
--start-stage
--stop-after
```

Only the following execution overrides are allowed:

```text
--dry-run
--resume
--force
--run-id
--output-format
--verbose
--keep-workspace
--fail-fast
```

Available reproducible configs:

```text
experiments/etl/tree2graph_smoke.yaml
experiments/etl/gpt_tests_vs_claude.yaml
experiments/etl/all_models_all_strategies.yaml
experiments/etl/thesis_final_evaluation.yaml
```

## Console summary and run metadata

Text output shows the `run-id`, overall status, and counters for each stage:

```text
Run: etl-tree2graph-001
Status: completed_with_failures
extraction: completed selected=1 created=1 failed=0
technical_validation: completed selected=1 passed=1 failed=0 skipped=0
reference_validation: completed selected=1 validated=1 invalid=0 skipped=0 infrastructure_errors=0
transformation_parsing: completed selected=4 passed=4 failed=0
transformation_validation: completed selected_suites=1 selected_transformations=4 execution_pairs=4 evaluated=4 passed=2 failed=2
```

`--output-format json` returns the same results in structured form.

Each non-dry run creates orchestration metadata only:

```text
Experiment_Runner/runs/<run-id>/
  manifest.json
  config.resolved.yaml
  stage_results.json
  summary.json
  runner.log
```

Detailed results remain owned by their respective components:

```text
Test_Generation/results/
ETL_Parser/results/
Transformation_Validation/results/
Transformation_Validation/artifacts/
```

All runtime results above are listed in `.gitignore`.

## Architectural responsibility

`Experiment_Runner` contains no extraction, Maven validation, ETL parsing, or
semantic test logic of its own. It is responsible only for application
orchestration: selection, stage ordering, dry-run, resume/force, run metadata,
and summaries.

```text
Experiment_Runner
  -> Test_Generation
  -> Transformation_Validation
  -> ETL_Parser and ETL_Test infrastructure
```

There are no reverse imports: `Test_Generation`, `Transformation_Validation`,
and `ETL_Parser` do not depend on `Experiment_Runner`.
