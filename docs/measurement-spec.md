# LLM4MTL — Measurement Specification

> Status: **authoritative frozen protocol for the controlled BA campaign.**
> Changing a numerator, denominator, population, exclusion rule, or the
> `T0 -> Tfinal` comparison is a scientific-method change.

## 1. Boundary

Metric calculation is standalone post-processing over immutable artifacts. It
does not participate in n8n routing or refinement, and held-out, mutation, and
coverage observations are written outside run directories.

The evaluation layer must not add production execution ledgers, duplicate
Surefire XML, add telemetry endpoints, instrument the engines, or migrate legacy
runs merely to calculate these metrics. Existing `suite_execution.json` and its
adjacent raw Maven/Surefire evidence remain authoritative for production
reference execution.

Cost, token, and latency telemetry are not among the eight metrics in this
campaign.

## 2. Campaign preflight

A campaign begins with an explicit `runs.txt`. Before any selected run is
evaluated, all selected runs must pass these checks:

1. `manifest.json` exists and is attributed to the selected run id;
2. `experiment_config` contains the two independent refinement budgets and the
   `parser_feedback`, `semantic_feedback`, and `source_diagnosis` flags;
3. terminal `result.json` exists and is attributed to the same run;
4. `T0` and all stored transformation refinements are individually recoverable,
   contiguous, and within the recorded transformation-refinement budget;
5. the raw artifacts required by the selected evaluator exist.

Failure is campaign-wide and occurs before evaluation output is written. Legacy
runs without `experiment_config` may be used for debugging but are excluded from
the controlled dataset; configuration is never inferred from a combined legacy
budget.

## 3. Suite reliability metrics

The primary unit is one generated semantic-test **suite**, because that is the
artifact passed through the production validation funnel.

```text
ExecutabilityRate_suite =
    executable generated suites / generated suites

ReferencePassRate_suite =
    executable suites passing the reference / executable generated suites
```

A suite is executable only when its stored observation has
`technically_executable == true`. It passes the reference only when the same
reference-role observation has `reference_valid == true`. A candidate without
an execution verdict is not executable; it is not silently removed from the
Executability Rate denominator. Per-test Surefire details are diagnostic, not a
replacement denominator.

## 4. Fixed held-out evaluation

Held-out semantic suites are fixed independently from production and are never
available to generation, feedback, diagnosis, or refinement. The standalone
runner executes the same stable held-out case ids against every stored
transformation iteration in temporary workspaces.

The headline comparison is always initial-to-final:

```text
T0 -> Tfinal
```

Intermediate `Ti -> Ti+1` results may be reported as trajectories but do not
change the following denominators.

### 4.1 Held-out Semantic Pass Rate

A transformation passes iff every held-out case is `PASS`:

```text
HeldoutSemanticPassRate =
    final transformations passing all held-out cases
    / evaluated final transformations
```

### 4.2 Held-out Repair Success Rate

The unit is a transformation, not an individual held-out case:

```text
RSR =
    #{T | T0 = FAIL and Tfinal = PASS}
    / #{T | T0 = FAIL and T was refined}
```

Here transformation `FAIL` means that not every held-out case passed. An
unrefined initially failing transformation is outside the denominator.

### 4.3 Regression Rate

The unit is one stable held-out case:

```text
RR =
    #{h | h(T0) = PASS and h(Tfinal) = FAIL}
    / #{h | h(T0) = PASS}
```

Technical `ERROR` and `NOT_RUN` outcomes remain explicit; they are not silently
relabelled as assertion failures.

## 5. Qualified mutation metrics

This campaign does not claim to decide semantic equivalence. It uses a frozen
qualified set:

```text
M_Q = mutants that are syntactically valid, executable, and observable
```

Qualification uses a fixed independent `qualification` suite population chosen
before evaluated generated suites. A mutant is observable when at least one
qualification suite passes the reference and reaches an assertion failure on the
mutant. Only qualification suites determine membership in `M_Q`; baseline and
generated suites can never add mutants to or remove mutants from the denominator.

An evaluated suite kills a qualified mutant iff it passes on the reference and
fails by evaluated assertions on the mutant. Parse, infrastructure, timeout, or
pre-assertion runtime errors are recorded but are not kills.

Let `K_G` be qualified mutants killed by generated suites and `K_B` those killed
by the baseline:

```text
MS_Q = |K_G ∩ M_Q| / |M_Q|

DeltaMS = |K_G \ K_B| / |M_Q|
```

The operator-set version, exact source replacement, source/mutant hashes, and
qualification facts are retained in the standalone mutant catalog. A change to
operators or qualification suites creates a new evaluation campaign version.

## 6. Metamodel EClass Coverage

Eligible EClasses are the input-side EMF `typesUsedInTransformation` in the
task contract. An EClass is covered when at least one generated semantic test
contains an instance in a `source` or `inout` model. For Reactions, an element
type explicitly created or manipulated by the test change sequence also counts.
Merely naming a type in an output assertion does not count.

```text
EClassCoverage =
    |union of covered eligible EClasses|
    / |eligible input EClasses|
```

This is calculated statically from stored `semantic_cases.json`, input models,
task contracts, and `.ecore` files. Plain-XML tasks have no EClass denominator;
their value is undefined rather than zero.

## 7. Missing data and derived outputs

Missing is distinct from zero. An undefined fraction retains numerator and a
zero denominator with a blank value. A required observation that is absent
causes evaluation failure rather than being fabricated as a pass, failure, or
zero.

The standalone layer writes reviewable CSVs only after raw observations are
available:

```text
immutable production artifacts
        +
fixed held-out / mutation inputs
        -> heldout.csv
        -> qualified-mutants.csv + mutation-observations.csv
        -> coverage.csv
        -> metrics.csv
```

Every per-run metric row retains language, task, pipeline variant, both
refinement budgets, and all three ablation flags. Aggregate rows expose their
population and denominator and do not invent a single configuration label for
mixed runs.
