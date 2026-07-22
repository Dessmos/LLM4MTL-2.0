# Experiment runner

llm4mtl.experiment_runner is the local orchestration CLI. Production routing
belongs to n8n; the runner invokes the same deterministic Python stages locally.

## Run a preset

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --config experiments/presets/etl/tree2graph_smoke.yaml

Use --dry-run to inspect selected responses, suites, transformations and
execution pairs without writing run artifacts.

## Active paths

- Test-generation responses: workflows/n8n/tests/mtl_snippets/ETL_test_generation/responses/
- Transformation responses: workflows/n8n/transformations/mtl_snippets/ETL_language/responses/
- Generated suites: artifacts/work/test_generation/generated_tests/etl/
- Run metadata: artifacts/work/runs/<run-id>/
- Parser and harness: engines/etl/{parser,harness}/

Resume an existing run without repeating selectors:

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --resume --run-id <run-id>

Run python -m llm4mtl.experiment_runner --help for individual tests and
transformations commands.
