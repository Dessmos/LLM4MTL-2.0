# Supplementary legacy-suite evaluation

This standalone offline assessment supplements the original generated-suite
RQ3/RQ4 results. It does not alter their population, metrics or canonical CSVs.
Original references, tests, fixtures and mutants are read-only inputs.

The completed campaign is in
`artifacts/legacy-suite-evaluation/campaign-20261008-v1/`. Its final report is
`report-v3/report.md`, and proposed thesis prose is `report-v3/thesis-additions.md`.
Earlier derived reports remain preserved. `report-reproduction-check/` is a
byte-identical independent reduction of the final report. Raw execution attempts
and freeze manifests are not overwritten by report generation.

## Execution and population

`protocol.py` defines scoring, task-specific Reactions contexts and exact archived
Tpre/Tpost endpoints. `run.py` freezes the 564 selected identities, the 120 pairs,
289 existing mutant identities, source hashes and dependency hashes before
execution. Every selected pair and every catalogue identity has a result,
including unavailable controls and technical failures. It never runs an optional
487-run T0 campaign.

`execution.py` copies engine templates into per-job temporary workspaces and runs
offline Maven `clean test` with the original method selectors. It records logs,
Surefire XML, source/fixture/dependency hashes, commands, duration and failures.
Timeouts kill the process group. Completion markers verify raw-file hashes and
allow resuming completed jobs without executing them again. There are no
outcome-seeking retries. Interrupted attempts remain alongside new attempts.

The temporary Reactions POM removes an unused unpublished metamodel dependency,
as the production adapter does. Original POMs remain unchanged. The candidate's
reaction/routines are composed into a fixed legacy segment; background blocks
are checked for unchanged contents. All original assertions remain intact.

## Reference controls and context limits

Initial reference qualification ran all 47 task configurations plus the twelve
full Reactions contexts and target-absent task-context controls. The initial
report was provided before candidate execution.

Additional dependency controls were separately frozen in
`artifacts/legacy-suite-evaluation/dependency-controls-20261008-v1/` after reference
qualification and before mutation execution. They remove only the target
reaction from the reference-composed context, retaining the reference routines.
Both primary and full contexts are checked for every Reactions task.

The full-context tests for `FamiliesToPersons_DeletedFamily` and
`NetworkToGraph_ComponentRenamed` pass even without the target reaction. Those
passes cannot qualify a candidate-specific oracle. `AmaltheaToAscet_TaskDeleted`
fails on the reference in both contexts. These three tasks' sixteen mutants
remain unavailable; no reference, assertion or prerequisite logic was repaired
to obtain a pass. The eleven additional full-context mutant slots are also
explicitly unavailable and do not enlarge the unique catalogue population.

Task-context Reactions evidence and full application integration are separate
populations. All twelve selected Reactions pairs belong to qualified tasks.
Full-context candidate compilation failures remain visible.

## Reproduction commands

Use a new output directory for a new campaign:

```sh
PYTHONPATH=pipeline/src:. .venv/bin/python -B -m evaluation.legacy_campaign.run --output artifacts/legacy-suite-evaluation/reproduction-new --phase freeze --workers 3 --timeout 300
PYTHONPATH=pipeline/src:. .venv/bin/python -B -m evaluation.legacy_campaign.run --output artifacts/legacy-suite-evaluation/reproduction-new --phase references
```

Inspect and report qualification before executing candidates. The remaining
phases of the same driver are `pairs`, `mutants`, and `integrity`. Reusing a
completed phase validates its evidence without rerunning completed jobs. The
`context_check` module separately freezes and runs `references` and `mutants`
phases for the additional context checks; use `--campaign` and `--output`.

To regenerate the completed report without Maven execution:

```sh
PYTHONPATH=pipeline/src:. .venv/bin/python -B -m evaluation.legacy_campaign.report --output artifacts/legacy-suite-evaluation/campaign-20261008-v1 --controls artifacts/legacy-suite-evaluation/dependency-controls-20261008-v1 --report artifacts/legacy-suite-evaluation/campaign-20261008-v1/report-new
```

The reducer applies explicit, logged corrections for two ATL methods whose
JUnit failure was recorded in stderr but whose Surefire testcase XML was lost
to a listener exception. Original raw classifications are preserved. No Maven
success without method evidence is treated as a semantic pass.

`reproduction-inputs.tar.gz` preserves the exact 6,158 protected input files.
`offline-maven-repository.tar.gz` preserves the copied dependency corpus;
archive inventories and SHA-256 provenance accompany both. The 534 cached JAR
hashes match the frozen dependency population. JDK/Maven version facts and
source implementation snapshots are stored in the freeze directory.

Observe the actual child JVM configuration: Surefire used JDK 17.0.19, Homebrew,
macOS aarch64, UTC, UTF-8, `user.language=ru`, `user.country=DE`. `MAVEN_OPTS`
sets English locale for the Maven parent; it did not force that locale in the
child. On another host, explicitly reproduce and verify these child properties.
The paired audit compares observed JVM properties, fixtures and dependency
classpaths with reference controls. Absolute archived paths refer to the
original workspace; relocating inputs requires an explicit provenance-aware
path rebinding rather than editing the frozen manifest in place.

## Scientific interpretation

Behavioral outcomes exclude twenty QVT-O smoke methods and the one weak
source-only Reactions method, while preserving their raw observations. Technical
recoveries are separate from observable assertion repairs. Later syntax repairs
are excluded in a named sensitivity population; full-context Reactions results
are another named sensitivity population. These views overlap by design and
must never be pooled as independent runs.

Mutation matching filters exactly the selected 564 run identities before any
grouping. Unique comparisons use `(language, task, operator)` and the union of
valid archived generated detections, with up to twelve opportunities per
identity. Repeated run-mutant observations are separately reported, never
treated as independent unique mutants. The matched denominator is not `M_Q`,
and no unqualified catalogue result is called `MS_Q`.

Archived generated matrix labels lack per-invocation source hashes and complete
failure/environment evidence. Current mutant bytes match the existing catalogue
hashes; strict historical byte/environment equivalence cannot be independently
recertified from those CSV labels alone. Inspected refinement prompts show no
original assertions, but complete initial requests and historical dirty execution
states were unavailable. Strict historical oracle independence is not claimed.

## Regression checks

```sh
.venv/bin/pytest -q pipeline/tests/test_legacy_campaign.py pipeline/tests/test_legacy_pilot.py
.venv/bin/pytest -q pipeline/tests
```

All observed empirical failures are results, not invitations to alter an oracle.
Compatibility: no existing schemas, CLI options, run manifests, references,
mutation operators or canonical evaluation CSVs are changed.
