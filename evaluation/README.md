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

## Refinement trajectory

`metrics.csv` reports the frozen `T0 -> Tfinal` comparison and nothing else. To
see how a refinement loop got there, derive a separate report from the same
`heldout.csv`:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.heldout.trajectory \
  --run-ids evaluation/runs.txt \
  --heldout evaluation/results/heldout.csv \
  --output evaluation/results/heldout-trajectory.csv
```

It writes one row per stored iteration, then one row per iteration cohort with
`run_id = ALL`. No metric numerator, denominator, or population changes: this
report is read alongside `metrics.csv`, never instead of it.

Three properties make the trend honest rather than merely pretty:

- runs end at different iterations, so a cohort row counts only the runs that
  actually reached that iteration and states it in `runs_in_cohort`. Finished
  runs are absent, not carried forward;
- `T0` has no previous iteration, so its four delta columns stay blank instead
  of reporting a zero-sized change;
- `repaired_*` and `regressed_*` count only `FAIL -> PASS` and `PASS -> FAIL`,
  matching the frozen regression definition. A case leaving `ERROR` or
  `NOT_RUN` never becomes a silent repair; it remains visible in `error_count`
  and `not_run_count`.

## Refinement loops per batch

To judge how many transformation refinement loops are worth running, tabulate
what every loop produced, straight from the pipeline's own recorded verdicts. It
needs no held-out suite and reads whole batches, including runs whose
transformation was never judged:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.refinement_loops \
  --batch batch_007 [--batch batch_008 ...] \
  --output-dir evaluation/results/batch_007
```

It writes:

- `refinement-loops-<language>.csv` — one row per run with its batch, model,
  strategy, budgets and flags, a `loop_<k>` column per loop, `loops_needed`
  (blank when never solved) and the run's `final_state`. A loop cell holds the
  latest `execution` outcome for that transformation iteration, else the latest
  `syntax-validation` outcome, else `DONE` (an earlier loop passed),
  `OVER_BUDGET`, `STOPPED` (the run ended before it), `NOT_JUDGED` or
  `UNFINISHED`;
- `refinement-loops-summary.csv` — per language, configuration and loop `k`:
  runs solved within `k` loops over the runs whose state at `k` is known
  (judged at `k` or later, or already passed), plus an `ALL` group per language;
- `refinement-loops.md` — the same tables, readable;
- `batch-runs.csv` — the whole batch in one table, one row per run of every
  language: configuration, `status`, `terminal_reason`, `suite_id`, the loop
  cells, `final_state`, `started_at`/`finished_at`/`duration_seconds`, and the
  summed `llm_call_observed` usage: `llm_calls`, `llm_latency_seconds`,
  `input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_tokens`,
  `total_tokens` (input + output). A field the run never recorded is blank,
  not zero.

`--drop-retried-orchestration-errors` leaves out a run that ended in
`ORCHESTRATION_ERROR` (n8n stopped; nothing was learned about the models) when
the same language and task also ended normally in the selected batches — the
case of a batch relaunched after a workflow crash. The dropped runs are listed
in `excluded-runs.txt`; a crashed run nothing replaced stays in the tables.

The verdict is the run's generated test, not a held-out suite. Like
`heldout-trajectory.csv`, this is a reporting view, not a campaign metric.

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

### Task × mutant table for one batch

A separate reporting mode, not `MS_Q`. For every run it runs the run's final
generated suite on the reference and then on each mutant of that task from
`evaluation/mutants/manifest.json`, and writes one row per run with a column per
operator (`M1`…`M8`): `KILLED`, `SURVIVED`, `PARSE_FAILED`, `ERROR`,
`NOT_JUDGED` (the suite fails on the reference, or the run has no suite) or
`N/A` (the operator does not apply to that task). `kill_rate` is killed over the
task's applicable mutants. It needs Maven and runs in UTC, as the stage service
does; otherwise date assertions differ and it refuses to start:

```bash
TZ=UTC PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.mutation.run_mutants \
  --batch batch_004 \
  --output evaluation/results/batch_004/mutants.csv
```

## Diagnosis agreement

Source Diagnosis gets one report per failing test case, so one broken
transformation that fails three cases yields three verdicts about one defect.
`diagnosis_aggregation` groups one execution attempt's reports by the failure
they describe (failure stage, exception type, normalized message, top stack
frame, transformation hash) and reports, per group, the verdicts it received and
how far they agree. It never changes a verdict and writes nothing; it prints
JSON:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.diagnosis_aggregation \
  --batch batch_004 --run <run-id> [--attempt N]
```

Without `--attempt` it reads the run's latest execution attempt. `agreement` is
null, not 1.0, when nothing was diagnosed.

## Failure analysis

`rq_metrics` counts the runs that succeeded; `failure_analysis` says why the
others did not. It reads the same selection and run facts, so its populations
are those of `rq-metrics.csv`, and writes four CSV files:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.failure_analysis \
  --output-dir artifacts/Chosen_for_evaluation/failure-analysis
```

- `failure-runs.csv` — one row per run: RQ1-RQ4 endpoints, the reason a run
  left the successful path, and per-stage failure classes and fingerprints;
- `failure-events.csv` — every stage attempt, diagnosis record and refinement
  of every run, in recorded order;
- `mutant-outcomes.csv` — one row per applicable mutant over the judged runs,
  with the construct it changes;
- `failure-crosstabs.csv` — diagnosis outcome by language, final recovery and
  routed artifact, and every failure class by stage and language. It also
  counts runs by first against last suite executability, and the RQ3
  population against whether the run spent any syntax refinement.

Failure classes come from fixed patterns over recorded messages; a message no
pattern matches stays in an `OTHER_*` class. `run_mutants` does not keep the
message of a mutant `ERROR`, so mutant errors are characterised per mutant, not
per run.

## Campaign composition

`campaign_composition` describes the selection behind `rq-metrics.csv`, the
same groups minus `excluded-runs.txt`:

```bash
PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.campaign_composition \
  --output-dir artifacts/Chosen_for_evaluation/campaign-composition
```

- `campaign-tasks.csv` — benchmark tasks per language and their share. It stops
  when the groups do not all cover the same task set.
- `campaign-configurations.csv` — evaluation groups and runs per configuration.
  A configuration is the model that fills every LLM role in the group's
  `batch.json`, or `mixed` when the roles use different models.

## Supplementary legacy-suite tables

Two read-only reductions rebuild the supplementary tables under
`artifacts/legacy-suite-evaluation/`. Each writes into a new directory, refuses
to overwrite one, and copies itself into its output as provenance:

```bash
PYTHONPATH=pipeline/src:. .venv/bin/python -m evaluation.reduce_tables \
  --output artifacts/legacy-suite-evaluation/<new-tables-directory>

PYTHONPATH=pipeline/src:. .venv/bin/python -m evaluation.reduce_metrics \
  --output artifacts/legacy-suite-evaluation/<new-rq-summary-directory>
```

- `reduce_tables` produced `tables-20261009-v1`. It recomputes
  `rq_metrics` and stops unless the result equals the stored `rq-metrics.csv`,
  so regenerate that file first whenever `rq_metrics` changes.
- `reduce_metrics` produced `rq-summary-20261012-v1`. Its `Snapshots.csv` and
  `Mutants.csv` are the inputs of `evaluation.equivalence_analysis` (PPL and
  mutation-score bounds). It takes the candidate LoC definition from
  `reduce_tables.code_loc`.

Paths:

- `reduce_tables`, `reduce_metrics` and `equivalence_analysis` name their input
  directories in constants at the top of each file, relative to the
  repository; change them there to point at other inputs.
- The legacy campaign artifacts recorded files by the absolute path of the
  machine that produced them. These three scripts rebase such paths onto the
  current checkout (`evaluation._common.repository_path`), and every path they
  write is repository-relative (`portable`). The same inputs therefore give
  byte-identical outputs on any machine and in any checkout location.
- `legacy_campaign/*`, `legacy_pilot/*`, `legacy_snapshots.py` and
  `mutation/equivalence_probes.py` are frozen: their file hashes are part of the
  campaign freezes and must not change. Their integrity checks still read the
  absolute paths recorded in `freeze.json`, so `legacy_campaign.report` (and
  the execution phases) only run where the repository sits at the recorded
  location. Its stored output, `campaign-20261008-v1/report-v3`, is what the
  other scripts read.

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
