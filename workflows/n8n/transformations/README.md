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
   cd 03-Code/Docker/n8n-docker
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

6. Run the workflows to generate prompts and evaluate model transformation code.  Results will be stored in the specified output directories on your host.

To stop the service, run:

```sh
docker compose down
```

## Folder overview

This directory contains:

- `docker-compose.yml` – defines the n8n service.
- `few_shot_examples/` – sample code snippets and prompts used for few‑shot prompting.
- `grammar/` – grammar definitions of the Reactions Language and ATL in EBNF format.
- `helper_methods/` – helper functions available to the language models during prompt construction.
- `models/` – example metamodel files referenced by the workflows.
- `mtl_snippets/` – sample model transformation code snippets.
- `workflows/` – the actual n8n workflow definitions (`*.json`) to be imported into the running instance.

Use this setup to replicate the evaluation pipeline described in the thesis or to experiment with new prompts and strategies.