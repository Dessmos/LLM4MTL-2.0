# Semantic-test pipeline

The semantic-test subsystem turns model output into deterministic, executable
JUnit suites and validates those suites before they can become an oracle.

The stages are:

1. extraction/ parses file-oriented model output into semantic_cases.json and
   generated model files.
2. codegen/ renders Java/JUnit deterministically.
3. technical_validation/ compiles and smoke-runs the candidate suite.
4. reference_validation/ checks the suite against the reference transformation.
5. suites/ contains shared discovery, metadata and injection primitives.

Active inputs live under:

    benchmark/tasks/etl/{references,task_contracts}/
    workflows/n8n/tests/mtl_snippets/ETL_test_generation/{prompts,responses}/
    prompt_assets/tests/{few_shot,grammar}/

Generated candidates and validation results live under
artifacts/work/test_generation/. The ETL harness source of truth is
engines/etl/harness/.
