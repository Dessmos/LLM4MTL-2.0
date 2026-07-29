# Transformation execution

This package executes validated generated test suites against generated ETL
transformations. It owns deterministic execution and evidence collection; it
does not make routing or LLM decisions.

Inputs:

    artifacts/work/test_generation/generated_tests/etl/<task>/candidates/<model>/<strategy>/<suite>/
    artifacts/work/runs/<run-id>/observations/
    artifacts/work/transformation_generation/etl/responses/<model>/<strategy>/<task>.etl

A candidate is eligible only when the supplied run-local observation records it
as reference-valid. Copied `validated/` directories are not read.

Run the facade from the repository root:

    PYTHONPATH=pipeline/src .venv/bin/python pipeline/src/llm4mtl/transformation_execution/validate_generated_transformations.py --observations-root artifacts/work/runs/<run-id>/observations --suite artifacts/work/test_generation/generated_tests/etl/Tree2Graph/candidates/gpt-5/few_shot/suite_001 --transformation artifacts/work/transformation_generation/etl/responses/gpt-5/grammar/Tree2Graph.etl

Results and injected Maven workspaces are written below
artifacts/work/transformation_validation/.
