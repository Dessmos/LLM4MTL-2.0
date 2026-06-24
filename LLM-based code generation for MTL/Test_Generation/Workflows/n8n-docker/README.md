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

Stop it with:

```sh
docker compose down
```

