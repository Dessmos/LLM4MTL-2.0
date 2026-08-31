# Offline evaluation

This directory is the standalone post-processing layer for the controlled BA
campaign. It does not call n8n, modify a run directory, duplicate Surefire XML
into a production ledger, or add runtime telemetry. Its only writes are derived
mutants and CSV files at paths explicitly supplied on the command line.

Run every command from the repository root with the pipeline package available:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.heldout.run_heldout ...
```

## Campaign preflight

`runs.txt` contains one run id per line. Before held-out, coverage, or aggregate
evaluation starts, every selected run must have:

- `manifest.json` with `pipeline_variant` and all five `experiment_config`
  fields;
- terminal `result.json` attributed to the same run;
- `transformation/iteration-000` and contiguous, unambiguous stored refinement
  iterations within the configured transformation budget.

One invalid selected run aborts the complete start. Legacy runs without
`experiment_config` are never silently mixed into the campaign.

## Held-out evaluation

The fixed suite root is versioned independently from production. Its layout is:

```text
heldout-v1/
  etl/
    Tree2Graph/
      metadata.json          # {"id": "tree2graph-heldout-v1"}
      semantic_cases.json    # stable case names such as H001
      models/
```

The evaluator renders the deterministic harness in a temporary directory and
runs the same suite against every stored transformation iteration:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.heldout.run_heldout \
  --run-ids evaluation/runs.txt \
  --tests-root evaluation/heldout/heldout-v1 \
  --output evaluation/results/heldout.csv
```

The headline comparison is always `T0 -> Tfinal`. Intermediate iterations stay
in the CSV for trajectory plots but do not change the Repair Success Rate or
Regression Rate denominators.

## Qualified mutation evaluation

`generate_mutants.py` applies exact, deterministic text replacements. A mutation
spec is ordinary JSON rather than a new production schema:

```json
{
  "operator_set_version": "etl-v1",
  "mutants": [
    {
      "mutant_id": "M001",
      "language": "etl",
      "task": "Tree2Graph",
      "operator": "delete_guard",
      "find": "guard-expression",
      "replacement": "true"
    }
  ]
}
```

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.mutation.generate_mutants \
  --spec evaluation/mutation/operators-v1.json \
  --output-root evaluation/results/mutants \
  --catalog evaluation/results/mutant-catalog.csv
```

The generated catalog deliberately leaves qualification facts blank: they have
not yet been observed. `run_mutants.py` consumes a suite CSV:

```csv
test_source,test_id,language,task,suite_path
qualification,Q001,etl,Tree2Graph,evaluation/mutation/qualification/etl/Tree2Graph/Q001
baseline,B001,etl,Tree2Graph,evaluation/mutation/baseline/etl/Tree2Graph/B001
generated,G001,etl,Tree2Graph,artifacts/work/test_generation/generated_tests/etl/Tree2Graph/candidates/model/strategy/suite
```

Every task must provide all three populations. Only `qualification` suites
decide whether a mutant is syntactically valid, executable, observable, and
therefore in `M_Q`; baseline and generated suites cannot change the denominator.

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.mutation.run_mutants \
  --catalog evaluation/results/mutant-catalog.csv \
  --suites evaluation/mutation/suites.csv \
  --qualified-catalog evaluation/results/qualified-mutants.csv \
  --output evaluation/results/mutation-observations.csv
```

## EClass coverage and aggregation

Coverage is static: an eligible EClass is covered by an instance in a generated
`source`/`inout` model. For Reactions, a type explicitly created or manipulated
by the change sequence also counts. Eligible classes are the input-side
`typesUsedInTransformation` from the task contract. Plain-XML tasks have an
undefined EClass denominator, represented by an empty metric value rather than
zero.

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.coverage.calculate_coverage \
  --run-ids evaluation/runs.txt \
  --output evaluation/results/coverage.csv

PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.calculate_metrics \
  --run-ids evaluation/runs.txt \
  --heldout evaluation/results/heldout.csv \
  --mutation-catalog evaluation/results/qualified-mutants.csv \
  --mutation-results evaluation/results/mutation-observations.csv \
  --coverage evaluation/results/coverage.csv \
  --output evaluation/results/metrics.csv
```

The aggregate script calculates:

- qualified mutation score over generated-suite kills;
- incremental mutation score, generated kills not already made by baseline;
- final held-out semantic pass rate;
- transformation-level held-out repair success rate;
- suite-level executability and reference-pass rates;
- EClass coverage;
- held-out per-case regression rate.

Undefined fractions keep a blank `value` with numerator and zero denominator
visible. Missing observations are errors, not zeros.
