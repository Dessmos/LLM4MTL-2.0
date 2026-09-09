# Experiment runner

llm4mtl.experiment_runner is the local orchestration which can MANUALLY start 
all Python stages that are als used in n8n workflow


# files description

_init_.py               - import 3 models: PipelineConfig, RunResult, StageResult
main.py and _main_.py   - points of entry (main.py is an old one)
models.py               - Data classes and contracts. Contains no logic
                                PipelineConfig - all what one run describes
                                StageResult    - Result of one stage
                                RunResult      - The whole run
config.py               - load and validation of configs
orchestrator.py         - main file of the folder.controls the whole process
cli.py                  - Command-line public contract (llm4mtl). Entry point for    
                            analyze command line for flags. And then gives it to orch.
matrix.py               - expands a single YAML list of settings into a list of 
                            specific runs.




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