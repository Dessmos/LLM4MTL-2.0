# Experiment runner

llm4mtl.experiment_runner is the local orchestration. It can start by hand
the same Python stages that the n8n workflow uses.


# files description

_init_.py               - import 3 models: PipelineConfig, RunResult, StageResult
_main_.py               - point of entry (python -m llm4mtl.experiment_runner)
models.py               - RunResult - the whole run. Contains no logic
                            (PipelineConfig and StageResult live in ../stages/models.py)
config.py               - load and validation of configs
orchestrator.py         - main file of the folder. Controls the whole run
cli.py                  - the `llm4mtl` command. Reads the command-line flags
                            and hands them to the orchestrator.
matrix.py               - expands a single YAML list of settings into a list of 
                            specific runs.

The stages themselves live in ../stages/. This folder only orders them, resumes
them and prints the summary. Nothing outside this folder imports it.




## Run a preset

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --config experiments/presets/etl/tree2graph_smoke.yaml


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

    .venv/bin/llm4mtl diagnosis report \
      --request artifacts/work/runs/<run-id>/diagnosis-request.json \
      --output artifacts/work/runs/<run-id>/diagnosis-evidence/<test-case>/<assertion>.json