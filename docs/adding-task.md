# Adding a benchmark task

> Status: active guide for the current benchmark layout.

A task is protected experimental input. Never edit a reference transformation,
metamodel, fixture, or contract merely to make a generated artifact pass.

## Current layout

Task inputs are grouped by language:

```text
benchmark/tasks/<lang>/
├── references/
│   └── <task>.<language-extension>
└── task_contracts/
    ├── <task>.json
    └── <task>.txt
```

Metamodels are stored under `benchmark/metamodels/`. The current ETL contract
builder also resolves legacy metamodel locations exposed by the frozen harness,
but new code must resolve repository paths through `llm4mtl.paths` and
`llm4mtl.conventions`.

The JSON contract is the machine-readable structural contract. The text form is
its deterministic prompt rendering. The reference transformation remains the
behavioural oracle.

## Steps

1. Add or reuse the required `.ecore` metamodels under `benchmark/metamodels/`.
2. Add the reference transformation as
   `benchmark/tasks/<lang>/references/<task>.<ext>`.
3. Add independent fixtures if the task or future qualification corpus needs
   them. Keep them under `benchmark/`; generated run inputs belong under
   `artifacts/work/`.
4. Generate or update the task contract deterministically.
5. Review runtime model names, roles, metamodel URIs, metamodel files, and
   available types in the generated JSON.
6. Add task-specific prompt examples only when they are genuinely required.
7. Add tests for contract enforcement and provenance hashes.

For ETL, the implemented generator is:

```bash
PYTHONPATH=pipeline/src .venv/bin/python \
  -m llm4mtl.task_contracts.build_task_model_contracts
```

It processes all ETL references by default. Use its explicit root arguments
when generating into a temporary directory for review. Do not run it against
protected contracts merely to repair a failing experiment.

Other languages need an equivalent deterministic contract builder before their
adapters are considered complete. The command should derive structural facts
from the language's reference/metamodel inputs rather than hand-maintained
duplicate mappings.

## Identity and provenance

One run fixes one concrete task. `task="all"` and `--all-tasks` are not valid run
identities; an experiment matrix must expand a task set into one run per task.

At run creation, provenance records hashes of:

- the reference transformation;
- the task contract;
- every metamodel named by the contract.

Missing protected inputs abort run creation. A run must never silently record a
null oracle or reuse an artifact from another task.

## Expected code impact

Adding another task for a language with a complete adapter should require task
inputs, generated contracts, prompt material, and tests—not changes to the
shared pipeline or engine code. If a task requires a new semantic scenario
concept, revise the shared domain contract explicitly instead of introducing a
task-name branch.
