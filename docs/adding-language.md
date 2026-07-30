# Adding a transformation language

> Status: active guide for the current adapter architecture.

A language extends the pipeline through the typed adapter boundary. It does not
copy the experiment runner, validation funnel, run store, stage service, or n8n
routing.

The four thesis languages are `etl`, `atl`, `qvto`, and `reactions`; all four
implement this contract. Their packages are the concrete examples to follow.

## Frozen engines

`engines/**` contains frozen legacy parsers and harnesses. Adding an adapter does
not author or refactor engine code. The adapter may:

- read an engine's declared version for provenance;
- invoke its parser through a structured command boundary;
- use its harness as a read-only template;
- execute only a materialized copy under the current run.

The shared engine directory must never receive generated tests, transformations,
temporary outputs, locks, or results.

## Required implementation

For `<lang>`, add:

```text
pipeline/src/llm4mtl/languages/<lang>/
├── __init__.py
├── adapter.py
└── rendering.py
```

The adapter structurally implements
`llm4mtl.languages.base.LanguageAdapter`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Sequence

from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.languages.base import Workspace


class ExampleAdapter:
    language_id = "example"
    renderer_version = "example-renderer-v1"

    def runtime_tool_versions(self) -> dict[str, str]:
        ...

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        ...

    def reference_transformation(self, task: str) -> Path:
        ...

    def validate_suite_artifacts(
        self,
        suite: GeneratedSuite,
    ) -> ArtifactValidation:
        ...

    def execute_suite(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        workspace: Workspace,
        timeout: int,
    ) -> SuiteExecutionObservation:
        ...

    def normalize_transformation_failure(
        self,
        observation: SuiteExecutionObservation,
    ) -> TransformationOutcome | None:
        ...

    def parse_transformations(
        self,
        transformations: Sequence[Path],
        workspace: Workspace,
    ) -> dict[Path, ParseObservation]:
        ...
```

Use `pipeline/src/llm4mtl/languages/etl/adapter.py` as the executable reference,
not as a source of ETL defaults for another language.

## Registration and conventions

1. Add an explicit `LanguageConfig` to
   `pipeline/src/llm4mtl/conventions.py`. Helpers require a language argument;
   there is no implicit ETL fallback.
2. Import and register the adapter in
   `pipeline/src/llm4mtl/languages/registry.py`.
3. Keep the registry static. There are four known implementations, so import
   scanning, entry points, and a plugin framework add no useful capability.
4. Keep extensions, parser commands, harness paths, renderer details, runtime
   model bindings, and engine diagnostics inside the language package.

Shared stages must not gain `if language == "<lang>"` branches.

## Semantic-test representation

The shared pipeline consumes language-neutral domain facts:

- `SemanticSuite` and `SemanticScenario`;
- named `ModelSlot` values instead of a fixed source/target pair;
- `batch_transformation` and `change_propagation` scenario kinds;
- declarative `ChangeOperation` values from the closed change vocabulary;
- `ArtifactValidation`, `ParseObservation`, and
  `SuiteExecutionObservation`;
- `TransformationOutcome` with named model snapshots.

ETL, ATL, and QVT-O normally render batch scenarios. Reactions must render
change-propagation scenarios deterministically; generated free-form change code
is not permitted.

The current `LanguageAdapter` covers the active generation/validation pipeline.
Mutation operators, reference instrumentation, and semantic snapshot comparison
have a different lifecycle and must be introduced as separate capabilities when
the measurement subsystem is implemented, rather than growing the adapter into
a God object.

## Task and prompt inputs

Add the language's protected task inputs as described in `adding-task.md`:

```text
benchmark/tasks/<lang>/references/
benchmark/tasks/<lang>/task_contracts/
```

Add semantic-test prompt assets. Every asset is language-scoped, and a workflow
only ever reads its own language's directory:

```text
prompt_assets/tests/few_shot/<lang>/test_generation_examples.txt
prompt_assets/tests/grammar/<lang>/EBNF.txt
prompt_assets/tests/helper_methods/<lang>/
```

The transformation side mirrors that layout under
`prompt_assets/transformations/`. Create the directory even when a language has
no helper methods to offer: the `Helper_methods` strategy flag exists for every
language, so its glob has to resolve for every language.

Add one reviewed prompt for each task:

```text
prompt_assets/task_prompts/<lang>/<task>.txt
```

Generate the four model-specific prompt-generation exports and synchronize the
test-generation exports with:

```bash
PYTHONPATH=pipeline/src .venv/bin/python \
  -m llm4mtl.prompt_assembly.n8n_exports --write
```

The prompt-generation exports enumerate references and call the stage service:

```text
/data/benchmark/tasks/<lang>/references/*
POST http://stage-service:8129/prompt-inputs/resolve
```

The service validates the matching task contract and returns the reference,
grammar, and only the exact metamodel files named by that contract. The raw
contract is not sent to the LLM. Prompt candidates are written to:

```text
/data/artifacts/task_prompt_candidates/<lang>/<model>/<task>.txt
```

After review, freeze one prompt under `/data/task_prompts/<lang>/<task>.txt`.
Both transformation-generation and test-generation exports read that same
file. Do not generate prompt text in Python and do not let downstream workflows
read candidates directly.

Transformation-generation assets predate this pipeline and are inputs to it;
the adapter does not generate transformations. Their exports live in
`workflows/n8n/transformations/workflows/<lang>_variants/` and are named
`Prompting_<LANG>_<model>_<strategy>.json`, where `<model>` and `<strategy>` are
spelled exactly as `experiments/matrices/*.yaml` spells them
(`only_prompt`, `grammar`, `few_shot`, `few_shots_AND_grammar`). The response
directory is derived from those same tokens and is how a stage selects a run's
responses, so a language that invents its own spelling produces results no
matrix can select.

## Required tests

Add contract and characterization coverage modelled on
`pipeline/tests/test_language_boundary.py`:

- the adapter satisfies `LanguageAdapter`;
- missing inputs fail closed;
- parser output becomes typed `ParseObservation` values;
- parser evidence is written under the supplied run-local observation path;
- the deterministic renderer emits no LLM-authored executable infrastructure;
- the harness command, timeout, classification, and cleanup are pinned;
- assertion failures are technically executable but reference-invalid;
- successful and attributable failure outcomes use the shared taxonomy;
- at least one representative scenario fits the shared domain model.

For Reactions, the representative case must exercise a real change-propagation
scenario. If that requires a Reactions-only field in the shared pipeline, revise
the domain contract before registering the adapter.

The opt-in real-engine gate is:

```bash
LLM4MTL_RUN_ENGINE_TESTS=1 .venv/bin/pytest -q \
  pipeline/tests/test_multilanguage_walking_skeletons.py::RealEngineWalkingSkeletonTests
```

It must pass before a new adapter is considered executable. Default Python tests
still validate deterministic rendering and all matrix inputs without invoking
Maven.

## What must remain unchanged

Adding a language must not require:

- provider-specific Python code or credentials;
- changes to existing stage implementations;
- a second run store or result schema;
- copied `validated/` suite directories;
- global CSV gates;
- writes to `engines/**`;
- language switches in the n8n main workflow.
