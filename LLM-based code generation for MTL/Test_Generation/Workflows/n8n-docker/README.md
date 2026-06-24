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
/data/snippets
/data/examples
/data/grammar
/data/models
/data/baseline/ETL_Test/resources
/data/baseline/ETL_Parser/resources
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
