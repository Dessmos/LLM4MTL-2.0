# n8n Docker Setup

This directory provides a Docker Compose configuration for running an [n8n](https://n8n.io/) instance locally.  The workflows supplied with this thesis automate prompt creation for large language models, invoke the models via API and run parser and unit tests on the generated code.  Running n8n in Docker ensures that the experiments are reproducible across different environments.

## Prerequisites

To use this setup you need:

- **Docker Desktop** installed on your machine.
  - On Windows you must also install **WSL 2** and a Linux distribution (e.g. Ubuntu) and select it under *Resources → WSL Integration* in the Docker Desktop settings.
- An API key for the language model provider (e.g. OpenAI) if you wish to run the workflows end‑to‑end.

## Setup and usage

Follow these steps to build and start the n8n container:

1. Open a terminal and navigate to this directory:

   ```sh
   cd workflows/n8n/transformations
   ```

2. Build and launch the services:

   ```sh
   docker compose up -d
   ```

   This command builds the n8n image with the required dependencies and also starts the container in the background.

3. Access the n8n web interface by opening [http://localhost:5678](http://localhost:5678) in your browser and choose your log in credentials.

4. Import the predefined workflows:

   - Click **Import** in the n8n UI.
   - Navigate to the `workflows/` folder in this directory and select the JSON files to import.

5. Configure credentials:

   - Open the **Credentials** section in n8n and add your API keys (e.g. OpenAI, Google Cloud).
   - Update the workflow nodes to reference your credentials if necessary.

6. Run the workflows to evaluate model transformation code. Transformation
   generation reads the same frozen
   `prompt_assets/task_prompts/<language>/<task>.txt` as semantic-test
   generation. New prompt-generation candidates are written separately under
   `artifacts/work/task_prompt_candidates/`.

To stop the service, run:

```sh
docker compose down
```

## Folder overview

This directory contains:

- `docker-compose.yml` – defines the n8n service and every read-only mount.
- `workflows/<lang>_variants/` – the n8n workflow definitions to import, one
  directory per language. Each holds `Prompt_generation_<lang>.json` plus one
  `Prompting_<LANG>_<model>_<strategy>.json` per model/strategy combination.
  Reactions drives its grid from the single matrix workflow under
  `workflows/updated_reactions_workflow/generate_reactions/` instead.

Read-only inputs come from the repository, never from a copy inside this
directory:

| Mount | Repository source |
|---|---|
| `/data/benchmark/tasks` | `benchmark/tasks/<lang>/` — references and contracts |
| `/data/models` | `benchmark/metamodels/` |
| `/data/task_prompts` | `prompt_assets/task_prompts/<lang>/` — the one reviewed prompt per task |
| `/data/examples` | `prompt_assets/transformations/few_shot/<lang>/` |
| `/data/grammar` | `prompt_assets/transformations/grammar/<lang>/` |
| `/data/helper_methods` | `prompt_assets/transformations/helper_methods/<lang>/` |

Every asset is read from its own language's subdirectory. Model and strategy
names are spelled exactly as `experiments/matrices/*.yaml` spells them
(`only_prompt`, `grammar`, `few_shot`, `few_shots_AND_grammar`), because the
response directory built from them is how a stage selects a run's responses.
The compose environment sets `N8N_RESTRICT_FILE_ACCESS_TO=/data`, which permits
n8n 2.x file nodes to access only this mounted workflow workspace.

Generated output paths:

```text
artifacts/work/task_prompt_candidates/<language>/<model>/
artifacts/work/transformation_generation/<language>/responses/
```

Use this setup to replicate the evaluation pipeline described in the thesis or to experiment with new prompts and strategies.
