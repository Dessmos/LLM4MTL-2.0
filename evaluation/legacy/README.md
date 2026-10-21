# Legacy significance analysis (pre-v5 study)

Frozen record of the statistics behind the earlier study: three LLMs
(`claude-sonnet-4`, `gemini-2-5-pro`, `gpt-5`) × prompting strategies
(`only_prompt` as baseline, `few_shot`, `grammar`, `few_shots_AND_grammar`)
generating ATL, ETL, QVTo and Reactions transformations. Nothing in the v5
pipeline or in `pipeline/tests` reads this directory, and it measures nothing
from `docs/measurement-spec.md`.

Per generated transformation the study recorded `Parsed`, `ProblemCount`
(→ `errors_per_LOC`, LOC of the reference), `CHRF_Score` and `test_pass`.
The scripts test:

- strategy vs baseline per LLM — Wilcoxon (continuous), one-sided McNemar
  (binary);
- LLMs within one strategy — Friedman (continuous), Cochran's Q (binary);
- `qvto/scripts/kruskal_wallis_by_mtl.py` — Kruskal–Wallis across LLMs per task.

## Layout

- `<lang>/<lang>_significance_tests.py` — the scripts that produced
  `<lang>/outputs/*.csv`. Their inputs are hard-coded Windows paths from the
  author's machine; they do not run from this repository.
- `<lang>/scripts/` — a CLI variant of the same tests (near-identical per
  language). It writes to `./outputs` in the current working directory, and its
  output format differs from the committed `outputs/*.csv`.
  `kruskal_wallis_by_mtl.py` is the exception: it always writes `kw_*.csv` into
  `qvto/outputs/`, whatever the working directory.
- `reactions/overall_significance/` — Reactions script and its CSVs. It reads
  `* (1).csv` names relative to the working directory.

## Inputs

The input data (`<lang>_test_results.csv`, generated transformations, ground
truth) lives in `engines/<lang>/harness` and `engines/<lang>/parser`. The
byte-identical copies that used to sit here were removed; the last commit
containing them is tagged `legacy-evaluation-snapshot`.

Run the CLI variant from a scratch directory so it does not overwrite anything
committed:

```bash
PYTHONPATH=<repo> <repo>/.venv/bin/python -m evaluation.legacy.etl.scripts.significance_test \
  --raw_csv <repo>/engines/etl/harness/etl_test_results.csv
```

`--gt_dir auto` searches next to the CSV and currently picks the Maven build
output under `engines/<lang>/parser/target/`.
