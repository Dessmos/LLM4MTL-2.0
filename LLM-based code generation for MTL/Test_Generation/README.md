# Test Generation

This folder contains the thesis extension for LLM-assisted semantic test generation.

The first vertical slice targets ETL `Tree2Graph`:

1. Generate semantic test suite candidates.
2. Validate generated suites against the reference `Tree2Graph.etl`.
3. Execute validated generated suites against parsable LLM-generated `Tree2Graph.etl` transformations.
4. Store all new metrics under `results/`.

The existing manual `ETL_Test/src/test/java/org/eclipse/epsilon/examples/etl/Tree2GraphTest.java`
may be used as an implementation example, but it is not part of this generated-test workflow.

## Layout Notes

Generated test suites are stored by language, task, LLM, prompting strategy, and suite id:

```text
generated_tests/<language>/<task>/candidates/<llm>/<strategy>/<suite_id>/
generated_tests/<language>/<task>/validated/<llm>/<strategy>/<suite_id>/
generated_tests/<language>/<task>/invalid/<llm>/<strategy>/<suite_id>/
```

Each suite should carry a `metadata.json` file describing the language, task, LLM,
strategy, prompt/workflow artifacts, raw output, and validation status.

Raw LLM responses should be stored under `raw_outputs/` before extracting files into
`generated_tests/`.

Prompt construction and LLM calls follow the baseline repository style: prompts live
inside n8n JSON workflow files under
`Workflows/n8n-docker/workflows/etl_variants/`, not as standalone Markdown prompt
templates. Generated prompt texts, references, and responses can be stored under
`Workflows/n8n-docker/mtl_snippets/ETL_test_generation/`.

The models under `Test_Generation/Workflows/n8n-docker/models` are prompt-context
copies. The source of truth remains the original `ETL_Test` resources.

## Tree2Graph Prompt Generation

The first implemented test-generation prompt is:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts/Tree2Graph.txt
```

It asks an LLM to generate an executable Java/JUnit semantic suite and requires
exact file blocks for:

```text
GeneratedTree2GraphSemanticTest.java
models/tree_simple.model
models/tree_branching.model
models/tree_deep.model
```

The production prompt-generation workflow is:

```text
Workflows/n8n-docker/workflows/etl_variants/Prompt_generation_tests_etl.json
```

It reads ETL reference transformations from:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/references/*.etl
```

and writes generated developer prompts to:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts/*.txt
```

The local Qwen workflow is only for infrastructure smoke testing and writes to:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts_smoke/
```

All `Prompting_tests_ETL_<llm>_<strategy>.json` workflows read production prompts
from:

```text
/data/snippets/ETL_test_generation/prompts/*.txt
```
