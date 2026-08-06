# Experiment runner

llm4mtl.experiment_runner is the local orchestration CLI. Production routing
belongs to n8n; the runner invokes the same deterministic Python stages locally.

## Run a preset

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --config experiments/presets/etl/tree2graph_smoke.yaml

Use --dry-run to inspect selected responses, suites, transformations and
execution pairs without writing run artifacts.

## Active paths

- Test-generation responses: artifacts/work/test_generation/etl/responses/
- Transformation responses: artifacts/work/transformation_generation/etl/responses/
- Generated suites: artifacts/work/test_generation/generated_tests/etl/
- Run metadata: artifacts/work/runs/<run-id>/
- Parser and harness: engines/etl/{parser,harness}/

Resume an existing run without repeating selectors:

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --resume --run-id <run-id>

Run python -m llm4mtl.experiment_runner --help for individual tests and
transformations commands.

## Prepare source-diagnosis evidence

After an execution attempt has recorded a parser-passing transformation and a
concrete semantic assertion failure, assemble the evidence through the same
orchestrator CLI:

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner diagnosis report \
      --request artifacts/work/runs/<run-id>/diagnosis-request.json \
      --output artifacts/work/runs/<run-id>/diagnosis-evidence/<test-case>/<assertion>.json

The request format and all required fields are documented in
`llm4mtl.semantic_tests.failure_report`. It identifies the immutable run
manifest, syntax and execution attempt evidence, generated/reference execution
observations, one `test_case_id`, one `assertion_id`, the structured comparator
difference, and any explicit snapshot, Surefire, or execution-log paths.

The command creates the output once and refuses to overwrite it. It also
verifies that the selected execution attempt, suite, transformation, Surefire
failure, and assertion message agree. Source-diagnosis evidence is emitted only
for `parser passed + assertions evaluated + semantic assertion failed`.

This command is deterministic post-processing, not an additional pipeline
stage. It does not call an LLM, classify the failure, modify run history, or
choose whether the transformation or test should be refined. n8n owns those
actions.
