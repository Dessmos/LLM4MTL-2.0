# Transformation execution

This package executes validated generated test suites against generated ETL
transformations. It owns deterministic execution and evidence collection; it
does not make routing or LLM decisions.

Default inputs:

    artifacts/work/test_generation/generated_tests/etl/<task>/validated/<model>/<strategy>/<suite>/
    workflows/n8n/transformations/mtl_snippets/ETL_language/responses/<model>/<strategy>/<task>.etl

Run the facade from the repository root:

    PYTHONPATH=pipeline/src .venv/bin/python pipeline/src/llm4mtl/transformation_execution/validate_generated_transformations.py --suite artifacts/work/test_generation/generated_tests/etl/Tree2Graph/validated/gpt-5/few_shot/suite_001 --transformation workflows/n8n/transformations/mtl_snippets/ETL_language/responses/gpt-5/grammar/Tree2Graph.etl

Results and injected Maven workspaces are written below
artifacts/work/transformation_validation/.
