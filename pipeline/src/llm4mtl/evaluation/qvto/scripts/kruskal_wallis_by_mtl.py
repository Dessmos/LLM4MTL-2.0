#!/usr/bin/env python3
"""
Kruskal-Wallis significance test: compare THREE LLM models within each MTL.

Methodology
-----------
For each MTL (transformation file) and each metric:
  - Groups   : 3 LLM models  (claude-sonnet-4, gemini-2-5-pro, gpt-5)
  - Obs/group: 4 values -- one per prompting strategy
               (only_prompt, few_shot, grammar, few_shot_AND_grammar)
  - Test     : Kruskal-Wallis H-test  (scipy.stats.kruskal)
  - alpha    : 0.05

Metrics
-------
  chrf             -- character-level F1 (chrF), continuous
  unparsed_rate    -- 1 if parse failed, 0 if parsed
  problems_per_LOC -- problem_count / reference-file LOC
  pass_at_1        -- 1 if functional test passes, 0 otherwise

Input
-----
  QVT-O Test/qvto_test_results.csv
      columns: model, strategy, file, problem_count, parse_success, chrF, test_pass

Output  (all in outputs/)
------
  kw_pvalues_by_mtl.csv  -- compact p-value table (rows=MTL, cols=4 metrics)
  kw_pertable.csv        -- paper-style: LLM means per strategy + KW p-value
  kw_detailed_table.csv  -- full per-model, per-strategy values + p-values

Usage
-----
  python scripts/kruskal_wallis_by_mtl.py
  python scripts/kruskal_wallis_by_mtl.py --csv "QVT-O Test/qvto_test_results.csv"
"""

import sys
import argparse
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import kruskal

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from .file_utils import find_ground_truth_dir, build_file_to_loc_mapping, match_file_to_ground_truth

warnings.filterwarnings("ignore")

# ── Constants ────────────────────────────────────────────────────────────────
STRATEGY_NORMALIZE = {
    "only_prompt/zero_shot": "only_prompt",
    "zero_shot":             "only_prompt",
}

STRATEGY_ORDER = ["only_prompt", "few_shot", "grammar", "few_shot_AND_grammar"]

METRICS = ["chrf", "unparsed_rate", "problems_per_LOC", "pass_at_1"]

METRIC_LABELS = {
    "chrf":             "ChrF",
    "unparsed_rate":    "Unparsed Rate",
    "problems_per_LOC": "Problems/LOC",
    "pass_at_1":        "Pass@1",
}

MODEL_ORDER = ["claude-sonnet-4", "gemini-2-5-pro", "gpt-5"]
MODEL_SHORT  = {
    "claude-sonnet-4": "Claude",
    "gemini-2-5-pro":  "Gemini",
    "gpt-5":           "GPT-5",
}


# ── Data loading ─────────────────────────────────────────────────────────────
def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [c.strip() for c in df.columns]
    df["strategy"] = df["strategy"].replace(STRATEGY_NORMALIZE)
    df["parse_success"] = df["parse_success"].map(
        lambda x: str(x).strip().lower() == "true"
    )
    if "test_pass" in df.columns:
        df["test_pass"] = df["test_pass"].map(
            lambda x: 1.0 if str(x).strip().lower() == "true"
                      else (0.0 if str(x).strip().lower() == "false" else np.nan)
        )
    else:
        df["test_pass"] = np.nan
    return df


def add_derived_metrics(df: pd.DataFrame, file_to_loc: dict) -> pd.DataFrame:
    df = df.copy()
    df["unparsed_rate"] = (~df["parse_success"]).astype(float)

    def get_loc(fname):
        loc = match_file_to_ground_truth(fname, file_to_loc)
        return float(loc) if loc and loc > 0 else np.nan

    df["ref_LOC"] = df["file"].apply(get_loc)
    df["problems_per_LOC"] = df["problem_count"] / df["ref_LOC"]
    df["pass_at_1"] = df["test_pass"]
    df["chrf"] = df["chrF"]
    return df


# ── Kruskal-Wallis: groups = LLM models ──────────────────────────────────────
def run_kruskal_wallis(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (MTL, metric): KW comparing 3 LLM groups.
    Each group's observations = values across all 4 strategies.

    Returns: file, metric, H, p_value, n_groups, reason
    """
    records = []
    for mtl in sorted(df["file"].unique()):
        df_mtl = df[df["file"] == mtl]
        for metric in METRICS:
            groups = []
            models_used = []
            for model in MODEL_ORDER:
                vals = df_mtl[df_mtl["model"] == model][metric].dropna().values
                if len(vals) > 0:
                    groups.append(vals)
                    models_used.append(model)

            if len(groups) < 2:
                records.append(dict(file=mtl, metric=metric,
                                    H=np.nan, p_value=np.nan,
                                    n_groups=len(groups),
                                    reason="fewer than 2 non-empty groups"))
                continue

            all_vals = np.concatenate(groups)
            if len(np.unique(all_vals)) == 1:
                records.append(dict(file=mtl, metric=metric,
                                    H=0.0, p_value=np.nan,
                                    n_groups=len(groups),
                                    reason="all values identical"))
                continue

            try:
                H, p = kruskal(*groups)
                records.append(dict(file=mtl, metric=metric,
                                    H=round(H, 4), p_value=round(p, 6),
                                    n_groups=len(groups), reason=""))
            except Exception as exc:
                records.append(dict(file=mtl, metric=metric,
                                    H=np.nan, p_value=np.nan,
                                    n_groups=len(groups), reason=str(exc)))

    return pd.DataFrame(records)


# ── Output builders ───────────────────────────────────────────────────────────
def build_pvalue_table(kw_results: pd.DataFrame) -> pd.DataFrame:
    """Compact pivot: rows=MTL, cols=4 metric p-values + sig flags."""
    pivot = kw_results.pivot(index="file", columns="metric", values="p_value")
    pivot = pivot[METRICS]
    pivot.columns = [f"p_{m}" for m in pivot.columns]
    pivot = pivot.reset_index()
    for m in METRICS:
        pivot[f"sig_{m}"] = pivot[f"p_{m}"].apply(
            lambda p: "*" if (not pd.isna(p) and p < 0.05) else ""
        )
    return pivot


def build_paper_style_table(df: pd.DataFrame, kw_results: pd.DataFrame) -> pd.DataFrame:
    """
    Paper-style table (rows = MTL x metric):
      - Per-model mean across 4 strategies
      - KW p-value testing whether models differ
    Columns: MTL | Metric | Claude | Gemini | GPT-5 | p-value | sig
    """
    rows = []
    for mtl in sorted(df["file"].unique()):
        df_mtl = df[df["file"] == mtl]
        for metric in METRICS:
            row = {"MTL": Path(mtl).stem, "Metric": METRIC_LABELS[metric]}
            for model in MODEL_ORDER:
                label = MODEL_SHORT[model]
                vals = df_mtl[df_mtl["model"] == model][metric].dropna().values
                row[label] = round(float(np.mean(vals)), 4) if len(vals) > 0 else np.nan

            kw_r = kw_results[
                (kw_results["file"] == mtl) & (kw_results["metric"] == metric)
            ]
            p = kw_r["p_value"].values[0] if len(kw_r) > 0 else np.nan
            row["p-value"] = round(float(p), 6) if not pd.isna(p) else "n/a"
            row["sig"] = "*" if (not pd.isna(p) and p < 0.05) else ""
            rows.append(row)

    model_labels = [MODEL_SHORT[m] for m in MODEL_ORDER]
    return pd.DataFrame(rows, columns=["MTL", "Metric"] + model_labels + ["p-value", "sig"])


def build_detailed_table(df: pd.DataFrame, kw_results: pd.DataFrame) -> pd.DataFrame:
    """
    Full detail: rows = (MTL, metric, model), cols = 4 strategies + KW p-value.
    Mean-across-strategies row added for each (MTL, metric, model).
    """
    rows = []
    for mtl in sorted(df["file"].unique()):
        df_mtl = df[df["file"] == mtl]
        for metric in METRICS:
            for model in MODEL_ORDER:
                df_m = df_mtl[df_mtl["model"] == model]
                row = {
                    "file":   mtl,
                    "metric": METRIC_LABELS[metric],
                    "model":  MODEL_SHORT[model],
                }
                for strat in STRATEGY_ORDER:
                    vals = df_m[df_m["strategy"] == strat][metric].dropna().values
                    row[strat] = round(float(vals[0]), 4) if len(vals) == 1 else np.nan
                row["mean_across_strategies"] = round(
                    float(df_m[metric].dropna().mean()), 4
                ) if len(df_m[metric].dropna()) > 0 else np.nan
                rows.append(row)

            # KW p-value row
            kw_r = kw_results[
                (kw_results["file"] == mtl) & (kw_results["metric"] == metric)
            ]
            p = kw_r["p_value"].values[0] if len(kw_r) > 0 else np.nan
            p_str = round(float(p), 6) if not pd.isna(p) else "n/a"
            sig_str = "*" if (not pd.isna(p) and p < 0.05) else ""
            prow = {
                "file":   mtl,
                "metric": METRIC_LABELS[metric],
                "model":  "KW p-value",
                "only_prompt": p_str, "few_shot": sig_str,
                "grammar": "", "few_shot_AND_grammar": "",
                "mean_across_strategies": "",
            }
            rows.append(prow)

    return pd.DataFrame(rows,
        columns=["file", "metric", "model"] + STRATEGY_ORDER + ["mean_across_strategies"])


# ── Console report ────────────────────────────────────────────────────────────
def print_report(paper_table: pd.DataFrame):
    model_labels = [MODEL_SHORT[m] for m in MODEL_ORDER]
    print("\n" + "=" * 90)
    print("KRUSKAL-WALLIS TEST: Comparing 3 LLM Models Within Each MTL")
    print("Groups: claude-sonnet-4 / gemini-2-5-pro / gpt-5")
    print("Obs per group: 4 (one per prompting strategy),  alpha = 0.05")
    print("=" * 90)

    for mtl in paper_table["MTL"].unique():
        sub = paper_table[paper_table["MTL"] == mtl]
        print(f"\n-- {mtl} " + "-" * 45)
        print(f"  {'Metric':<20}", end="")
        for lbl in model_labels:
            print(f"  {lbl:>14}", end="")
        print(f"  {'p-value':>10}  sig")
        print("  " + "-" * 76)
        for _, row in sub.iterrows():
            print(f"  {row['Metric']:<20}", end="")
            for lbl in model_labels:
                v = row[lbl]
                print(f"  {v:>14.4f}" if not pd.isna(v) else f"  {'N/A':>14}", end="")
            print(f"  {str(row['p-value']):>10}  {row['sig']}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="KW test comparing 3 LLM models per MTL")
    ap.add_argument("--csv", default=None,
                    help="Input CSV path (default: auto-detect)")
    ap.add_argument("--gt_dir", default="auto",
                    help="Ground-truth .qvto directory (default: auto)")
    args = ap.parse_args()

    repo_root = SCRIPT_DIR.parent

    # Locate CSV
    if args.csv:
        csv_path = Path(args.csv)
    else:
        csv_path = repo_root / "QVT-O Test" / "qvto_test_results.csv"
        if not csv_path.exists():
            csv_path = repo_root / "QVT-O parser" / "benchmark_results_detailed.csv"
    if not csv_path.exists():
        print(f"ERROR: Cannot find input CSV at {csv_path}", file=sys.stderr)
        sys.exit(1)
    print(f"Input CSV : {csv_path}")

    # Locate ground-truth directory
    if args.gt_dir == "auto":
        gt_dir = find_ground_truth_dir(str(repo_root))
    else:
        gt_dir = args.gt_dir

    if gt_dir is None:
        print("WARNING: Ground-truth directory not found; problems_per_LOC will be NaN")
        file_to_loc = {}
    else:
        print(f"GT dir    : {gt_dir}")
        file_to_loc = build_file_to_loc_mapping(gt_dir)
        loc_summary = ", ".join(f"{k}={v}" for k, v in sorted(file_to_loc.items()))
        print(f"LOC map   : {len(file_to_loc)} files -> {loc_summary}")

    # Load data
    print("\nLoading data ...")
    df_raw = load_data(str(csv_path))
    df = add_derived_metrics(df_raw, file_to_loc)
    print(f"Strategies: {sorted(df['strategy'].unique())}")
    print(f"Models    : {sorted(df['model'].unique())}")
    print(f"MTL files : {sorted(df['file'].unique())}")
    print(f"Rows      : {len(df)}")

    # Run KW tests
    print("\nRunning Kruskal-Wallis tests (groups = 3 LLM models) ...")
    kw_results = run_kruskal_wallis(df)

    # Build tables
    pvalue_table   = build_pvalue_table(kw_results)
    paper_table    = build_paper_style_table(df, kw_results)
    detailed_table = build_detailed_table(df, kw_results)

    # Save outputs
    out_dir = repo_root / "outputs"
    out_dir.mkdir(exist_ok=True)
    f1 = out_dir / "kw_pvalues_by_mtl.csv"
    f2 = out_dir / "kw_pertable.csv"
    f3 = out_dir / "kw_detailed_table.csv"
    pvalue_table.to_csv(f1, index=False)
    paper_table.to_csv(f2, index=False)
    detailed_table.to_csv(f3, index=False)
    print(f"\nSaved -> {f1}")
    print(f"Saved -> {f2}")
    print(f"Saved -> {f3}")

    # Console report
    print_report(paper_table)

    # Summary
    total  = len(kw_results)
    sig    = (kw_results["p_value"] < 0.05).sum()
    na_cnt = kw_results["p_value"].isna().sum()
    print(f"\n{'='*60}")
    print(f"Total KW tests   : {total}  (10 MTLs x 4 metrics)")
    print(f"Significant (*) : {sig}  ({100*sig/total:.0f}%)")
    print(f"Non-calculable  : {na_cnt}")
    if na_cnt > 0:
        for reason in kw_results.loc[kw_results["p_value"].isna(), "reason"].unique():
            cnt = (kw_results["reason"] == reason).sum()
            print(f"   - {reason}  ({cnt}x)")
    print("=" * 60)


if __name__ == "__main__":
    main()
