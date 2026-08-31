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
| Held-out Repair Success Rate | adopted `transformation/iteration-NNN/` plus fixed-suite observations derived by `evaluation/heldout/run_heldout.py` | available offline at transformation level (`T0 -> Tfinal`) |
| Held-out Semantic Pass Rate | fixed versioned held-out suites plus `evaluation/results/heldout.csv` | available offline; held-out data never enters production feedback |
| Qualified Mutation Score | frozen mutation spec, generated source/hash catalog, independent qualification suites, and `mutation-observations.csv` | available through standalone mutation scripts |
| Incremental Mutation Score | the same qualified catalog and explicit baseline/generated rows in `mutation-observations.csv` | available offline over the same `M_Q` |
| Metamodel EClass Coverage | stored generated `semantic_cases.json` and input models plus benchmark task contracts and `.ecore` files | available by static offline analysis; no instrumentation |
| Regression Rate | stable held-out case ids in `heldout.csv` at `T0` and `Tfinal` | available offline at held-out-case level |

Every run used by a metric experiment must also have an immutable
`manifest.json`. Runs created by the master record `pipeline_variant` and
`experiment_config`, including independent test/transformation refinement
budgets and the parser-feedback, semantic-feedback, and source-diagnosis flags.
Legacy manifests without `experiment_config` fail campaign preflight and are
excluded, not assigned inferred defaults.

Derived CSVs belong outside run directories. They retain run ids and grouping
configuration and never replace or rewrite raw facts.
