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

Metamodels are stored under `benchmark/metamodels/`. Every non-null
`models[].metamodelFile` must be the exact repository-relative path to the
metamodel used by that task. The prompt-input resolver follows only these paths;
there is no language-wide directory fallback.

The JSON contract is the machine-readable structural contract. The text form is
its deterministic contract rendering, not the standalone prompt produced by
the prompt-generation LLM. The reference transformation remains the behavioural
oracle.

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
6. Run prompt generation and review its candidate under
   `artifacts/work/task_prompt_candidates/<lang>/<model>/<task>.txt`.
7. Freeze exactly one approved prompt as
   `prompt_assets/task_prompts/<lang>/<task>.txt`. Both transformation and
   semantic-test generation read this same file.
8. Add tests for exact input resolution, contract enforcement, and provenance
   hashes.

One generator covers every language:

```bash
PYTHONPATH=pipeline/src .venv/bin/python \
  -m llm4mtl.task_contracts.build_language_task_contracts --language <lang>
```

It processes all of that language's references by default. Use its explicit root
arguments when generating into a temporary directory for review. Do not run it
against protected contracts merely to repair a failing experiment.

The builder derives runtime slots and metamodel aliases from the reference,
namespace/classifier facts from protected Ecore inputs, and a source hash from
the reference bytes. Contracts have one shape in every language: `schemaVersion`,
`task`, `language`, `transformation`, `reference`, `sourceHash`, `models`, and
`rules`, with `typesUsedInTransformation` on each model. Review the generated
files before committing them.

`sourceHash` is enforced, not decorative: editing a reference without rebuilding
its contract makes prompt-input resolution fail for that task rather than
silently describing metamodels the reference no longer uses.

Add the task name to the corresponding `experiments/matrices/thesis-<lang>.yaml`.
`pipeline/tests/test_multilanguage_walking_skeletons.py` checks that every
matrix task has a matching reference and machine-readable contract and that
each language has grammar and few-shot prompt resources.

Run the selected n8n `prompt_generation` workflow. Its LLM output is a candidate
task prompt:

```text
artifacts/work/task_prompt_candidates/<lang>/<model>/<task>.txt
```

Review it before replacing
`prompt_assets/task_prompts/<lang>/<task>.txt`. Then run transformation
generation and test generation; both consume that one frozen file. The test LLM
writes its untrusted response as `.md` beneath the corresponding
`responses/<model>/<strategy>/` directory.

## Identity and provenance

One run fixes one concrete task. `task="all"` and `--all-tasks` are not valid run
identities; an experiment matrix must expand a task set into one run per task.

At run creation, provenance records hashes of:

- the reference transformation;
- the task contract;
- every metamodel named by the contract;
- the frozen task prompt shared by both generators.

Missing protected inputs abort run creation. A run must never silently record a
null oracle or reuse an artifact from another task.

## Expected code impact

Adding another task for a language with a complete adapter should require task
inputs, generated contracts, prompt material, and tests—not changes to the
shared pipeline or engine code. If a task requires a new semantic scenario
concept, revise the shared domain contract explicitly instead of introducing a
task-name branch.
