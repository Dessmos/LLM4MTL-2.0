# Reactions Language & ATL Transformation Projects

This repository contains several modules that demonstrate model transformations and synchronisation using the Reactions Language, the ATLAS Transformation Language (ATL) and related tooling.  It also includes an `n8n` setup to automate parts of the workflow.

## Modules

- **Reactions_Language_Parser** – a Maven module that builds a shaded JAR capable of parsing and validating Reactions Language code.  See [`Reactions_Language_Parser/README.md`](Reactions_Language_Parser/README.md) for details.
- **Reactions_Language_Tests** – tests written using the Vitruv Methodologist template to validate Reactions Language transformations on a Virtual Single Underlying Model (V‑SUM).  See [`Reactions_Language_Tests/README.md`](Reactions_Language_Tests/README.md).
- **ATL_Tests** – example transformations written in the ATLAS Transformation Language (ATL) along with JUnit tests for scenarios such as Amalthea‑to‑Ascet, Families‑to‑Persons and Network‑to‑Graph.  See [`ATL_Tests/README.md`](ATL_Tests/README.md).
- **Docker** – a Docker Compose configuration for running an `n8n` instance.  The provided workflows automate the creation of prompts and evaluation of generated code.  See [`Docker/n8n-docker/README.md`](Docker/n8n-docker/README.md).

## Building the code

All modules use Maven.  To compile and run the tests for all modules at once, execute:

```sh
mvn clean verify
```

## Running tests

The test suites in `Reactions_Language_Tests` and `ATL_Tests` can be run from your IDE or via Maven.  These tests instantiate metamodels, run the transformations and assert structural and semantic correctness of the results.

## Automated prompt generation and prompting

The `Docker/n8n-docker` module contains an `n8n` workflow that automates the generation of prompts for large language models, the invocation of the models (e.g. via the OpenAI API) and the execution of parser and unit tests on the generated code.  This workflow is central to reproducing the evaluation results and can be run locally via Docker.

Refer to the individual module readmes for further usage instructions.
