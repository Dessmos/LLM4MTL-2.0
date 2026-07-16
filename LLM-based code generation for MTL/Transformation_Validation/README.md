# Generated Transformation Validation

This stage executes reference-validated generated test suites against LLM-generated
ETL transformations.

Inputs remain owned by their producing stages:

```text
Test_Generation/generated_tests/etl/<task>/validated/<test_model>/<test_strategy>/<suite_id>/
Workflows/n8n-docker/mtl_snippets/ETL_language/responses/<transformation_model>/<transformation_strategy>/<task>.etl
```

Every execution is archived under `artifacts/etl/<task>/<passed|failed>/...` with
an immutable copy of the transformation, the validated suite, the complete Maven
output, and machine-readable metadata. A compact index is appended to
`results/etl/<task>/generated_transformation_validation.csv`.

## Usage

Run all matching validated suites and generated transformations:

```bash
python3 Transformation_Validation/scripts/etl/validate_generated_transformations.py
```

Run one pair:

```bash
python3 Transformation_Validation/scripts/etl/validate_generated_transformations.py \
  --suite Test_Generation/generated_tests/etl/Tree2Graph/validated/gpt-5/few_shot/suite_001 \
  --transformation Workflows/n8n-docker/mtl_snippets/ETL_language/responses/gpt-5/grammar/Tree2Graph.etl
```

Useful filters are `--task`, `--test-model`, `--test-strategy`,
`--transformation-model`, and `--transformation-strategy`. Use `--dry-run` to
inspect the selected pairs without modifying `ETL_Test` or creating artifacts.

The runner temporarily injects the selected transformation, Java tests, and test
models into `ETL_Test`. All injected source/resource files are restored even when
Maven fails or times out.
