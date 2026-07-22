# LLM4MTL

LLM4MTL is an experiment pipeline for generating and evaluating model
transformations with large language models. n8n owns LLM calls and routing;
Python performs deterministic extraction, validation, execution and evaluation.

## Repository layout

- pipeline/ — the installable llm4mtl Python package, tests and stage HTTP service.
- engines/ — language-specific parsers and Maven test harnesses.
- benchmark/ — task contracts, references, metamodels and fixtures.
- prompt_assets/ — grammar, few-shot examples and helper material.
- workflows/n8n/ — transformation/test workflows and the master scaffold.
- experiments/ — presets, variants and experiment matrices.
- schemas/ — JSON contracts shared by n8n, Python and stored artifacts.
- artifacts/work/ — generated per-run output; intentionally not tracked by Git.

See docs/architecture.md for ownership rules and docs/data-flow.md for the
end-to-end flow.

## Python setup and tests

    python3 -m venv .venv
    .venv/bin/pip install -e 'pipeline[dev]'
    .venv/bin/pytest -q pipeline/tests

Run a non-mutating selection check:

    PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.experiment_runner pipeline run --config experiments/presets/etl/tree2graph_smoke.yaml --dry-run

Maven modules are built from their engine directories, for example:

    mvn -f engines/etl/parser/pom.xml verify
    mvn -f engines/etl/harness/pom.xml verify

## n8n and stage service

- Transformation workflows: workflows/n8n/transformations/
- Test-generation workflows: workflows/n8n/tests/
- Master workflow scaffold: workflows/n8n/main/
- Python stage service: pipeline/stage_service/

Each directory contains its own deployment or import instructions. API keys stay
in n8n credentials and are never passed to the Python subsystem.
