# Legacy-suite feasibility pilot

This is a supplementary offline assessment. It does not change the populations,
metrics or frozen files governed by [measurement-spec.md](../../docs/measurement-spec.md).
The executor is deliberately bounded to four named batch-014 runs and two
existing mutants per task. It has no full-campaign mode and makes no LLM calls.

- `assessment.py`: validates selected identities, hashes and T0/Tpre/Tpost;
  maps all 47 tasks to 70 existing methods in 38 Java classes.
- `independence.py`: scans saved prompt/request evidence and recovers older task
  prompt bytes from Git using recorded SHA-256 hashes. Missing initial assembled
  requests remain unknown.
- `run_pilot.py`: materializes isolated engines and an isolated copy of the local
  Maven cache; executes Maven offline; preserves source, logs, Surefire XML,
  dependency hashes and input fingerprints. Reactions context is explicitly fixed.
- `summarize.py`: reduces saved evidence without rerunning transformations.
- `pipeline/tests/test_legacy_pilot.py`: checks endpoint selection, context
  composition, classification and the semantic-kill gate.

T0 is the saved initial generated output. Tpre is the saved input named by the
first semantic-refinement request. Tpost is the last saved version, including
any subsequent syntax repair. The complete version census retains missing runs.

The Reactions pilot uses `FamiliesToPersons_CreatedFather`. Its minimal context
retains exact original root-registration and candidate-task blocks, with the
original `familiesToPersons` segment name. Candidate routines replace only their
reference counterparts. The original Java methods and their stimuli are unchanged.
Context definitions for the other eleven Reactions tasks are not implemented.

Each new execution output path must not exist. The default runs the minimal
Reactions context. To reproduce the earlier full-context experiment, use
`--reactions-context full`. Do not use an existing evidence directory.

```sh
PYTHONPATH=pipeline/src .venv/bin/python -B -u -m evaluation.legacy_pilot.run_pilot --output /tmp/new-legacy-pilot --reactions-context minimal --timeout 300
PYTHONPATH=pipeline/src .venv/bin/python -B -m evaluation.legacy_pilot.independence --output /tmp/new-independence.json --historical-output /tmp/new-historical-prompts.json
```

The performed pilot evidence is in `artifacts/legacy-test-pilot/`. Its first
full-context Reactions Tpre/Tpost/control builds failed Xtext validation. The
initial classifier called these infrastructure errors. The final summary records
them as compilation errors with `observed=false`, retains their original labels,
and preserves all raw logs in the first execution directory. The minimal-context
check uses the same run and mutants; it does not replace an unsuccessful sample.

The final evidence reduction was run as follows:

```sh
PYTHONPATH=pipeline/src .venv/bin/python -B -m evaluation.legacy_pilot.summarize --first artifacts/legacy-test-pilot/pilot-20261008-01 --minimal artifacts/legacy-test-pilot/pilot-20261008-02-minimal-reactions --independence artifacts/legacy-test-pilot/independence-20261008-v2.json --historical artifacts/legacy-test-pilot/historical-task-prompt-evidence-v2.json --output artifacts/legacy-test-pilot/summary-20261008-v2
```

All test outcomes remain explicit. A semantic kill requires a reference-passing
behavioral method, an assertion failure on the mutant, and no technical errors in
the evaluated mutant suite. Resource smoke, execution smoke and source-only weak
methods cannot produce kills under this conservative pilot policy. An exception
inside an assertion expression remains a runtime error. `PRESENT` in the existing
catalogue does not establish qualified-set membership; this pilot reports no MS_Q.

Validation performed:

```sh
.venv/bin/pytest -q pipeline/tests/test_legacy_pilot.py
.venv/bin/pytest -q pipeline/tests
```

The final narrow run passed 9 tests and 4 subtests. The final complete run passed
621 tests and 2635 subtests, with 1 existing opt-in real-engine walking-skeleton
test skipped and 1 existing Starlette/httpx deprecation warning. Maven results
are experimental observations, including the deliberately retained failures.
