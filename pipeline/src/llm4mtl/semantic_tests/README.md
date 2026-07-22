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
templates. The ETL workflows are split by pipeline stage:

```text
Workflows/n8n-docker/workflows/etl_variants/prompt_generation/
Workflows/n8n-docker/workflows/etl_variants/test_generation/
```

Generated prompt texts, references, and responses can be stored under
`Workflows/n8n-docker/mtl_snippets/ETL_test_generation/`.

The models under `Test_Generation/Workflows/n8n-docker/models` are prompt-context
copies. The source of truth remains the original `ETL_Test` resources.

## Semantic Case Schema

Generated-test responses should not contain Java/JUnit as the primary artifact.
The expected Plan B output is:

```text
semantic_cases.json
models/<generated-input>.model
models/<generated-input>.xml
```

`semantic_cases.json` is task-generic. It describes how the deterministic
harness should run ETL and what observable target-model facts should be checked:

```json
{
  "schemaVersion": 1,
  "testClass": "GeneratedTransformationSemanticTest",
  "transformation": "transformations/<Task>.etl",
  "metamodels": [
    "metamodels/Source.ecore",
    "metamodels/Target.ecore"
  ],
  "tests": [
    {
      "name": "case name",
      "models": [
        {
          "name": "Source",
          "kind": "emf",
          "role": "source",
          "path": "models/input.model",
          "generated": true,
          "metamodelUri": "Source"
        },
        {
          "name": "Target",
          "kind": "emf",
          "role": "target",
          "metamodelUri": "Target"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Target",
          "type": "Element",
          "expected": 3
        },
        {
          "kind": "featureValues",
          "model": "Target",
          "type": "Element",
          "feature": "name",
          "expected": ["a", "b", "b"]
        },
        {
          "kind": "referencePairs",
          "model": "Target",
          "type": "Relationship",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            {"source": "a", "target": "b"}
          ]
        }
      ]
    }
  ]
}
```

Supported model kinds:

```text
emf
plainXml
```

Supported assertion kinds:

```text
count
featureValues
pathValues
objects
referencePairs
```

The deterministic generator compares repeated values as multisets. This means
cases such as three target elements with the same `name` are valid and are not
collapsed through Java `Set` semantics.

The extraction layer still accepts the older Tree2Graph-only fields
`inputModel`, `expectedNodes`, and `expectedEdges` as a compatibility adapter,
but new prompts should use the task-generic schema above.

## Prompt Generation

Before running test generation, build the deterministic model contracts and
production prompts locally:

```bash
PYTHONPATH=Test_Generation/scripts python3 Test_Generation/scripts/etl/build_task_model_contracts.py
PYTHONPATH=Test_Generation/scripts python3 Test_Generation/scripts/etl/build_task_prompts.py --llm gpt-5
```

The first command writes task contracts under:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/task_contracts/
```

The second command writes production prompts under:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts/gpt-5/*.txt
```

Each contract separates ETL runtime model names from EMF metamodel URIs. For
example, `Flowchart!Flowchart` uses runtime model name `Flowchart` but
metamodel URI `flowchart`; `OO2DB!TypeMapping` uses runtime model name `OO2DB`
but metamodel URI `TM`; `RSS`/`Atom` are `plainXml` runtime models. Production
prompts and test-generation workflows must treat these contracts as ground
truth and must not invent model names, metamodel URIs, XML namespaces, or type
names.

The n8n prompt-generation workflows are draft-only experiments:

```text
Workflows/n8n-docker/workflows/etl_variants/prompt_generation/Prompt_generation_tests_ETL_gpt-5.json
Workflows/n8n-docker/workflows/etl_variants/prompt_generation/Prompt_generation_tests_ETL_claude-sonnet-4.json
Workflows/n8n-docker/workflows/etl_variants/prompt_generation/Prompt_generation_tests_ETL_gemini-2-5-pro.json
```

They read ETL reference transformations from:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/references/*.etl
```

For `gpt-5`, draft prompt candidates are written by the prompt-generating LLM
to:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompt_drafts/gpt-5/*.txt
```

Draft prompts are not consumed by the production test-generation workflows. The
`prompts/gpt-5/*.txt` production prompts are generated by
`build_task_prompts.py` so deterministic contract and task-context sections
cannot be overwritten by another LLM.

The LLM-specific production prompt folder is consumed by the next stage:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts/gpt-5/*.txt
```

The local Qwen workflow is only for infrastructure smoke testing and writes to:

```text
Workflows/n8n-docker/workflows/etl_variants/prompt_generation/Prompt_generation_tests_ETL_qwen2-5-coder-7b.json
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts_smoke/qwen2-5-coder-7b/
```

To smoke-test the next step with local Qwen, import and run:

```text
Workflows/n8n-docker/workflows/etl_variants/test_generation/Prompting_tests_ETL_qwen2-5-coder-7b_only_prompt.json
```

It reads Qwen-generated prompt files from:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/prompts_smoke/qwen2-5-coder-7b/*.qwen-smoke.txt
```

and writes raw Markdown test-suite responses to:

```text
Workflows/n8n-docker/mtl_snippets/ETL_test_generation/responses/qwen2-5-coder-7b/only_prompt/*.md
```

These Qwen outputs are for cheap local workflow checks. They can still be passed
through extraction and technical validation, but they are not the main thesis
LLM result set unless explicitly promoted.

Production `Prompting_tests_ETL_<llm>_<strategy>.json` workflows read selected
production prompts from the LLM-specific prompt folder. The current `gpt-5`
workflows use:

```text
/data/snippets/ETL_test_generation/prompts/gpt-5/*.txt
```

The test-generation workflows are stored under:

```text
Workflows/n8n-docker/workflows/etl_variants/test_generation/
```

Generated Markdown responses are extracted into candidate suites by the generic
extractor:

```text
scripts/etl/extract_generated_suite.py
```

It maps each response file name to the task name. For example:

```text
responses/gpt-5/grammar/Tree2Graph.md -> generated_tests/etl/Tree2Graph/candidates/gpt-5/grammar/suite_XXX/
responses/gpt-5/grammar/OO2DB.md      -> generated_tests/etl/OO2DB/candidates/gpt-5/grammar/suite_XXX/
```

Use `scripts/etl/extract_generated_suite.py --task Tree2Graph` when only the
first Tree2Graph slice should be extracted.

## Python Script Layout

The runnable files under `scripts/etl/` are intentionally thin wrappers. The
editable implementation is split by responsibility:

```text
scripts/common/                    # shared paths, CSV, injection, Maven helpers
scripts/etl/suites/                # shared suite metadata, Java path, and injection helpers
scripts/etl/extraction/            # Markdown response discovery/parsing/writing
scripts/etl/technical_validation/  # suite discovery, Java/model checks, smoke tests
scripts/etl/reference_validation/  # reference ETL injection, Maven execution, promotion
```

This keeps command compatibility while making the workflow internals easier to
edit in smaller files.

Language-specific filesystem conventions are centralized in
`scripts/common/paths.py` via `LanguageConfig`. The current default is ETL, but
new language workflows should add their own config instead of hardcoding roots
inside validation or extraction modules.
