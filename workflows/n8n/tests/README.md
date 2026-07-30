# n8n Test Generation

This Docker Compose setup runs a separate n8n instance for the test-generation
workflow.

Start it from this directory:

```sh
docker compose up -d
```

Open n8n at:

```text
http://localhost:5679
```

This instance is intentionally separate from the baseline n8n setup, which uses
port `5678`.

Mounted paths inside the container:

```text
/data/workflows
/data/artifacts
/data/benchmark/tasks
/data/task_prompts
/data/examples
/data/grammar
/data/diagnosis_prompts
```

Immutable references and contracts remain under `benchmark/`; the stage service
resolves exact metamodel files from its repository mount. Grammar, few-shot
assets, and frozen task prompts remain under `prompt_assets/`.

Run the selected model's `prompt_generation` workflow to create a review
candidate. The stage service resolves
`reference → task_contract → exact task-specific metamodels`, and n8n invokes
the LLM with those files and the grammar:

```text
artifacts/work/task_prompt_candidates/<language>/<model>/<task>.txt
```

Evaluation does not read this directory. Review the candidate and deliberately
replace the corresponding
`prompt_assets/task_prompts/<language>/<task>.txt`. Both transformation and
test generation read this same frozen file.

Run the matching `test_generation` workflow. It invokes the test-generation LLM
and writes:

```text
artifacts/work/test_generation/<language>/responses/<model>/<strategy>/<task>.md
```

File access is explicitly restricted to the mounted workflow workspace:

```text
N8N_RESTRICT_FILE_ACCESS_TO=/data
```

If n8n shows `Access to the file is not allowed`, recreate the container after
changing the Docker Compose environment:

```sh
docker compose down
docker compose up -d
```

Stop it with:

```sh
docker compose down
```
