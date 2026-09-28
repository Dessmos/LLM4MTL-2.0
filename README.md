# LLM4MTL

LLM4MTL is a research pipeline for generating and evaluating model transformations using large language models. It currently supports the ETL, ATL, QVT-O, and Reactions languages ​​and approaches.

For each task in the benchmark, the pipeline generates a transformation and a set of semantic test cases. First, the selected tests are validated against a manually created reference transformation. Tests that pass this validation are then used to evaluate the generated transformation. In the event of a failure, the pipeline can identify the cause and adjust either the tests or the transformation itself, within a specified iteration limit.

All deterministic operations and their results are saved to disk, enabling subsequent analysis and evaluation of the task execution process.

## Running the pipeline

The standard setup uses Docker and the Compose plugin. Docker Desktop is
sufficient on macOS and Windows; on Linux, install Docker Engine and the
Compose plugin. An OpenAI credential is the simplest way to run the complete
pipeline. Anthropic and Google calls require the LiteLLM setup described in
[docs/model-selection.md](docs/model-selection.md).

From the repository root, build and start n8n and the stage service:

```bash
docker compose -f workflows/n8n/tests/docker-compose.yml up -d --build
```

This starts n8n at <http://localhost:5679>. The stage service is not published
to the host by this Compose file, but its health endpoint can be checked from
the n8n container:

```bash
docker exec n8n-test-generation wget -qO- http://stage-service:8129/health
```

The expected response is `{"status":"ok"}`.

### n8n setup

1. Open <http://localhost:5679> and create the local n8n owner account.
2. Create the required provider credential in n8n.
3. Import `workflows/n8n/main/llm4mtl-agent-workflow.json`.
4. Configure the model and credential in the workflow's model nodes.
5. Execute the workflow and complete the **Configure and Start Pipeline**
   form.

Generated subworkflows refer to provider credentials through
`PROVIDER_CREDENTIALS` in
`pipeline/src/llm4mtl/prompt_assembly/n8n_exports/workflow_graph.py`. On a
fresh n8n installation, update the credential ID and regenerate the exports:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.prompt_assembly.n8n_exports --write
```

The launch form supports test-only, transformation-only, and full runs. It
also selects languages, tasks, providers, prompt strategies, refinement
limits, and experiment variants. The form fields are described in
[workflows/n8n/main/README.md](workflows/n8n/main/README.md).

Stop the containers with:

```bash
docker compose -f workflows/n8n/tests/docker-compose.yml down
```

The n8n account, credentials, and imported workflow remain in the Docker
volume. Passing `-v` to the command also removes that volume.

The stage service can be run separately and published on
<http://localhost:8129>:

```bash
docker compose -f pipeline/stage_service/docker-compose.yml up -d --build
```


## Local development

Python 3.11 or newer is required. Java 17 and Maven are also needed when a test
uses a real language engine.

```bash
python3 -m venv .venv
.venv/bin/pip install -e 'pipeline[dev]'
.venv/bin/pytest -q pipeline/tests
```

There is no local command-line runner for the pipeline. Runs are started
through n8n and the stage service. After changing prompt assets or the export
generator, regenerate the n8n workflows with:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m llm4mtl.prompt_assembly.n8n_exports --write
```

Maven modules are built from their engine directories, for example:

```bash
mvn -f engines/etl/parser/pom.xml verify
mvn -f engines/etl/harness/pom.xml verify
```


## Architecture

The system is divided between n8n orchestration and a Python stage service.
This is the main architectural boundary in the project.

| Component | Responsibilities |
| --- | --- |
| n8n | Selects providers, models, prompt strategies, and experiment variants; stores credentials; calls LLMs; applies retry and routing policy; records provider-reported usage and latency. |
| Python | Extracts and validates generated artifacts; renders the Java test harness; invokes parsers and Maven; records stage results, evidence, and run artifacts. |

Python does not call LLM providers or decide which stage runs next. Each stage
returns a factual `status` and `outcome_code`; n8n uses those values to choose
the next transition. The FastAPI service is only the transport layer between
n8n and the Python stage implementations.

```text
Browser
  |
  v
n8n master workflow --------> LLM providers
  |
  | HTTP/JSON
  v
Python stage service
  |
  v
Shared Python stages
  |-- run store --------> artifacts/work/
  `-- language adapter -> run-local Java parser and Maven/JUnit harness
```

n8n and the stage service normally run as Docker containers on the same
network. The stage service is available to n8n at
`http://stage-service:8129`.

### Run lifecycle

1. The master workflow creates one batch for the launch and one run for each
   selected language/task pair. The run's `manifest.json` fixes its identity
   and provenance and is not modified afterwards.
2. n8n calls the configured LLMs and passes their responses to Python for
   storage and deterministic processing. Model information, token usage, and
   latency are recorded with the run.
3. Python extracts the declarative semantic cases and model files, ignores any
   LLM-written Java infrastructure, and renders the JUnit harness.
4. Candidate tests are run against the reference transformation. A test that
   fails on the reference is not used as an oracle.
5. The generated transformation is parsed and then executed against the
   qualified tests.
6. On failure, Python prepares a report. n8n may request diagnosis and
   refinement, subject to the configured iteration limit.
7. Stage attempts and supporting evidence are appended to the run. The final
   run status is derived from those stored facts.

The full data flow is documented in [docs/data-flow.md](docs/data-flow.md).
Stage identifiers, outcome codes, and transition rules are defined in
[docs/n8n-python-contract.md](docs/n8n-python-contract.md).

## Repository layout

```text
.
├── pipeline/                 Python package, tests, and stage-service deployment
│   ├── src/llm4mtl/          importable `llm4mtl` package
│   ├── tests/                Python test suite
│   └── stage_service/        Dockerfile and Compose configuration
├── workflows/n8n/            orchestration workflows
│   ├── main/                 launch form and master state machine
│   ├── tests/                semantic-test generation workflows
│   ├── transformations/      transformation generation workflows
│   └── subworkflows/         shared workflows, including failure diagnosis
├── schemas/                  JSON contracts shared across system boundaries
├── benchmark/                metamodels, task contracts, and reference transformations
├── prompt_assets/            task prompts, grammars, examples, and diagnosis prompts
├── experiments/              experiment variants and matrices
├── engines/                  language parsers and Maven/JUnit harnesses
├── evaluation/               offline metrics, mutation analysis, and held-out suites
├── baseline/                 frozen results from earlier runs
├── artifacts/work/           generated run output (not tracked by Git)
└── docs/                     architecture, API, data-flow, and measurement documents
```

### Python package

Most of the code under active review is in `pipeline/src/llm4mtl/`.

```text
pipeline/src/llm4mtl/
├── domain/
├── external_tools/
├── languages/
├── prompt_assembly/
├── run_store/
├── semantic_tests/
├── serialization/
├── stage_service/
├── stages/
├── task_contracts/
├── workspace/
├── __init__.py
├── artifact_schemas.py
├── conventions.py
├── paths.py
├── provenance.py
├── stage_contract.py
├── stage_recording.py
└── vocabulary.py
```

#### Folders

| Folder | What is inside |
| --- | --- |
| `domain/` | The basic objects used throughout the pipeline: test cases, observations, and results. This folder describes the data but does not read files or run programs. |
| `external_tools/` | Small wrappers that start Maven and the language parsers, then collect their output and errors. |
| `languages/` | The code specific to ETL, ATL, QVT-O, and Reactions. Each language has its own rules for creating and running tests. |
| `prompt_assembly/` | Collects the files needed for prompts, prepares refinement prompts, and creates the n8n workflow JSON files. |
| `run_store/` | Creates batch and run folders and saves manifests, events, attempts, and final results. |
| `semantic_tests/` | Turns an LLM response into test files, builds the Java test project, runs the checks, and prepares failure reports. |
| `serialization/` | Reads and writes JSON files and calculates file hashes. |
| `stage_service/` | The web API used by n8n to create runs and start pipeline steps. |
| `stages/` | The actual pipeline steps: extraction, syntax checking, technical checking, reference checking, and execution. |
| `task_contracts/` | Reads the fixed description of each benchmark task: its reference transformation, metamodels, and the model types that may be used. It uses this information to check generated tests. |
| `workspace/` | Creates a private working copy of the required engine for each run. |

#### Python files in the package root

| File | What it does |
| --- | --- |
| `__init__.py` | Marks this directory as the `llm4mtl` package and stores the package version. |
| `artifact_schemas.py` | Checks JSON data against the files in `schemas/` before the data is saved. |
| `conventions.py` | Keeps the language names and the usual folder names for ETL, ATL, QVT-O, and Reactions in one place. |
| `paths.py` | Defines where the main repository folders and generated run folders are located. |
| `provenance.py` | Records which Git revision, tool versions, and input files were used for a run. |
| `stage_contract.py` | Converts the result of a Python step into the standard response that n8n expects. |
| `stage_recording.py` | Saves the start and end of one step, together with its result and supporting files. |
| `vocabulary.py` | Keeps the shared names for model families, prompt strategies, and pipeline steps. |

The rest of the package shares the objects defined in `domain/`. Pipeline steps
use one common language interface, so they do not need separate ETL, ATL,
QVT-O, or Reactions code. The full set of dependency rules is explained in
[docs/architecture.md](docs/architecture.md).

## Documentation

| Topic | Document |
| --- | --- |
| Architecture and ownership | [docs/architecture.md](docs/architecture.md) |
| End-to-end data flow | [docs/data-flow.md](docs/data-flow.md) |
| Measurement and evaluation | [docs/measurement-spec.md](docs/measurement-spec.md) |
| n8n/Python stage contract | [docs/n8n-python-contract.md](docs/n8n-python-contract.md) |
| Stage service API | [docs/runner-api.md](docs/runner-api.md) |
| Model and provider selection | [docs/model-selection.md](docs/model-selection.md) |
| Adding a language | [docs/adding-language.md](docs/adding-language.md) |
| Adding a task | [docs/adding-task.md](docs/adding-task.md) |
| Adding a provider | [docs/adding-provider.md](docs/adding-provider.md) |
| Offline evaluation | [evaluation/README.md](evaluation/README.md) |

Contributor and repository rules are documented in [AGENTS.md](AGENTS.md).
