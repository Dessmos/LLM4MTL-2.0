# Metric experiment raw data

Metrics are derived after pipeline execution. n8n records orchestration and LLM
facts; it does not calculate experiment metrics.

Before starting a metric experiment, its row below must name immutable raw
artifacts that already exist, or define and test the missing artifact contract.
An experiment must not start when its raw-data source is marked `not defined`.

| Metric | Authoritative raw data | Current state |
| --- | --- | --- |
| Test Executability Rate | `artifacts/work/runs/<run_id>/observations/**/suite_execution.json`; supporting Maven output and Surefire XML under the adjacent `execution_evidence/` | available at suite level |
| Reference-Pass Rate | the same reference-role `suite_execution.json`, keyed by its recorded suite and reference-transformation hashes | available at suite level |
| Repair Success Rate | `generations/<artifact>/iteration-NNN/generation.json`, `refinements/<artifact>/iteration-NNN/request.json`, immutable stage attempts, adopted `transformation/iteration-NNN/`, and terminal `result.json` | internal trajectory available; independent held-out verdict not defined |
| Held-out Semantic Pass Rate / Pass@1 | not defined | blocked until held-out identity, prompt/feedback exclusion, and per-test outcomes have an immutable contract |
| Mutation Score | not defined | blocked until `Q`, the qualified catalog `M_Q`, and mutant-by-test execution facts from `measurement-spec.md` are implemented |
| Incremental Mutation Score | not defined | blocked until baseline/generated test roles and the mutant-by-test matrix are implemented |
| Metamodel Coverage | not defined | blocked until eligible and covered element sets and instrumentation provenance are implemented |
| Regression Rate | not defined | blocked until stable test identities and per-iteration held-out outcomes are implemented |

Every run used by a metric experiment must also have an immutable
`manifest.json`. Runs created by the master record `pipeline_variant` and
`experiment_config`, including independent test/transformation refinement
budgets and the parser-feedback, semantic-feedback, and source-diagnosis flags.
Legacy manifests without `experiment_config` must be treated as configuration
unknown, not assigned inferred defaults.

Derived tables, rates, and statistical tests belong under the experiment-level
artifact store. They must cite the run ids and raw artifact paths they consumed;
they must never replace or rewrite those raw facts.
