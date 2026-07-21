# Adding a new task

> Status: **skeleton (Stage 0)**.

A task is a bundle under `benchmark/tasks/<lang>/<task>/`:

```text
task.yaml       # description + roles + references to metamodels in the registry
reference/      # the reference (golden) transformation — behavioural oracle
fixtures/       # input models
contract.json   # GENERATED from the metamodels (source_hash); do not hand-edit
```

Steps:
1. Add or reuse metamodels in `benchmark/metamodels/<mm>/`.
2. Write `task.yaml` pointing at those metamodels.
3. Add the reference transformation and fixtures.
4. Generate the contract (`llm4mtl contracts generate <lang>/<task>` — Stage 1+),
   which is verified against the metamodels in CI.
5. Add prompting material if the task needs task-specific examples.

No pipeline or engine code changes are required to add a task.
