"""
Significance tests for QVTo benchmark results.

Two types of tests:
  *  : strategy significantly better than Baseline, per LLM
         - Continuous (ChrF, errors_per_LOC): Wilcoxon signed-rank test (one-sided)
         - Binary (Parsed, Pass@1): McNemar's test (one-sided, exact binomial)
  Underline: LLMs differ significantly within a strategy
         - Continuous (ChrF, errors_per_LOC): Friedman test
         - Binary (Parsed, Pass@1): Cochran's Q test

LOC definition: ground truth QVTo file lines, excluding blank lines and '--' comments.
Note: Baseline = 'only_prompt' (Gemini) or 'only_prompt/zero_shot' (GPT, Claude).
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats

# ---------------------------------------------------------------------------
# Ground truth LoC: count non-blank, non-comment lines from .qvto files
# QVTo comment syntax: lines starting with '--'
# ---------------------------------------------------------------------------
GT_DIR = Path(r"C:\Users\10239\OneDrive\Desktop\QVT-O siginificanttest\QVT-O Test\qvto-tests\src\main\resources\transformations")

def count_loc_qvto(file_path):
    """Count LOC excluding blank lines and '--' comment lines."""
    loc = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("--"):
                loc += 1
    return loc

FILE_LOC = {p.stem: count_loc_qvto(p) for p in GT_DIR.glob("*.qvto")}
print("Ground truth LoC per file:")
for name, loc in sorted(FILE_LOC.items()):
    print(f"  {name:<30} {loc}")

# ---------------------------------------------------------------------------
# Load & preprocess
# ---------------------------------------------------------------------------
df = pd.read_csv(
    r"C:\Users\10239\OneDrive\Desktop\QVT-O siginificanttest\QVT-O Test\qvto_test_results.csv"
)

# Normalise column names to match ETL script conventions
df = df.rename(columns={
    "model":         "LLM",
    "strategy":      "Strategy",
    "file":          "File",
    "problem_count": "ProblemCount",
    "parse_success": "Parsed",
    "chrF":          "CHRF_Score",
})

# Strip .qvto extension from File
df["File"] = df["File"].str.replace(r"\.qvto$", "", regex=True)

# Normalise bool columns
for col in ("Parsed", "test_pass"):
    df[col] = df[col].map({True: 1, False: 0, "True": 1, "False": 0,
                           "true": 1, "false": 0})

# Combined pass@1
df["pass1"] = ((df["Parsed"] == 1) & (df["test_pass"] == 1)).astype(int)

# errors_per_LOC
df["reference_LOC"] = df["File"].map(FILE_LOC)
df["errors_per_LOC"] = df["ProblemCount"] / df["reference_LOC"]

# ---------------------------------------------------------------------------
# Strategy mapping
# Both 'only_prompt' (Gemini) and 'only_prompt/zero_shot' (GPT, Claude)
# are the Baseline condition.
# ---------------------------------------------------------------------------
STRATEGY_MAP = {
    "only_prompt":          "Baseline",
    "only_prompt/zero_shot": "Baseline",
    "few_shot":              "Few-shot",
    "grammar":               "Grammar",
    "few_shot_AND_grammar":  "FS + GR",
}
LLM_MAP = {
    "gpt-5":           "GPT",
    "gemini-2-5-pro":  "Gemini",
    "claude-sonnet-4": "Claude",
}
df["Strategy"] = df["Strategy"].map(STRATEGY_MAP)
df["LLM"]      = df["LLM"].map(LLM_MAP)

STRATEGIES = ["Few-shot", "Grammar", "FS + GR"]
LLMS       = ["GPT", "Gemini", "Claude"]
FILES      = sorted(df["File"].unique())
ALPHA      = 0.05

# ---------------------------------------------------------------------------
# Helper: get per-file array for (strategy, llm, metric)
# ---------------------------------------------------------------------------
def get_vals(strategy, llm, metric):
    sub = df[(df["Strategy"] == strategy) & (df["LLM"] == llm)]
    return sub.set_index("File").reindex(FILES)[metric].values.astype(float)

# ---------------------------------------------------------------------------
# Cochran's Q test (binary_matrix: shape n_blocks x k_treatments)
# ---------------------------------------------------------------------------
def cochrans_q(binary_matrix):
    data = np.asarray(binary_matrix, dtype=float)
    n, k = data.shape
    C = data.sum(axis=0)
    L = data.sum(axis=1)
    N = data.sum()
    denom = k * N - np.sum(L ** 2)
    if denom == 0:
        return np.nan, np.nan
    Q = (k - 1) * (k * np.sum(C ** 2) - N ** 2) / denom
    p = 1 - stats.chi2.cdf(Q, df=k - 1)
    return float(Q), float(p)

# ---------------------------------------------------------------------------
# McNemar's test (one-sided: treatment better than baseline)
# ---------------------------------------------------------------------------
def mcnemar_one_sided(base_bin, treat_bin):
    base_bin  = np.asarray(base_bin,  dtype=int)
    treat_bin = np.asarray(treat_bin, dtype=int)
    b = int(np.sum((base_bin == 0) & (treat_bin == 1)))
    c = int(np.sum((base_bin == 1) & (treat_bin == 0)))
    if b + c == 0:
        return np.nan
    p = stats.binomtest(b, b + c, 0.5, alternative="greater").pvalue
    return float(p)

# ---------------------------------------------------------------------------
# Wilcoxon signed-rank test (one-sided)
# ---------------------------------------------------------------------------
def wilcoxon_greater(base_vals, treat_vals):
    """Treatment significantly higher than baseline."""
    if np.all(treat_vals - base_vals == 0):
        return np.nan
    try:
        _, p = stats.wilcoxon(treat_vals, base_vals, alternative="greater")
        return float(p)
    except ValueError:
        return np.nan

def wilcoxon_less(base_vals, treat_vals):
    """Treatment significantly lower than baseline (lower is better)."""
    if np.all(treat_vals - base_vals == 0):
        return np.nan
    try:
        _, p = stats.wilcoxon(treat_vals, base_vals, alternative="less")
        return float(p)
    except ValueError:
        return np.nan

def fmt_p(p):
    return f"{p:.4f}" if (p is not None and not np.isnan(p)) else "  n/a"

def fmt_stat(s):
    return f"{s:.4f}" if (s is not None and not np.isnan(s)) else "n/a"

# ---------------------------------------------------------------------------
# 1. STAR (*): each strategy vs Baseline, per LLM
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("STAR (*) TESTS  --  strategy vs Baseline, per LLM")
print("=" * 65)

# (metric, label, kind, higher_is_better)
METRICS_STAR = [
    ("CHRF_Score",     "ChrF",        "continuous", True),
    ("errors_per_LOC", "Errors/LoC",  "continuous", False),
    ("Parsed",         "Parsability", "binary",     True),
    ("pass1",          "Pass@1",      "binary",     True),
]

star_results = {}

for metric, label, kind, higher_better in METRICS_STAR:
    direction = "higher" if higher_better else "lower"
    print(f"\n--- {label} ({kind}, {direction} is better) ---")
    baseline_vals = {llm: get_vals("Baseline", llm, metric) for llm in LLMS}

    for strategy in STRATEGIES:
        row = []
        for llm in LLMS:
            treat_vals = get_vals(strategy, llm, metric)
            base_vals  = baseline_vals[llm]

            if kind == "continuous":
                p = wilcoxon_greater(base_vals, treat_vals) if higher_better \
                    else wilcoxon_less(base_vals, treat_vals)
            else:
                p = mcnemar_one_sided(base_vals, treat_vals)

            sig = (p is not None) and not np.isnan(p) and (p < ALPHA)
            star_results[(metric, strategy, llm)] = (p, sig)
            marker = "*" if sig else " "
            row.append(f"{llm}:{fmt_p(p)}{marker}")
        print(f"  {strategy:<12}  " + "   ".join(row))

# ---------------------------------------------------------------------------
# 2. UNDERLINE: across LLMs within a strategy
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("UNDERLINE TESTS  --  LLMs differ within a strategy")
print("=" * 65)

METRICS_UL = [
    ("CHRF_Score",     "ChrF",        "continuous"),
    ("errors_per_LOC", "Errors/LoC",  "continuous"),
    ("Parsed",         "Parsability", "binary"),
    ("pass1",          "Pass@1",      "binary"),
]

underline_results = {}

for metric, label, kind in METRICS_UL:
    print(f"\n--- {label} ({kind}) ---")

    for strategy in ["Baseline"] + STRATEGIES:
        matrix = np.column_stack([get_vals(strategy, llm, metric) for llm in LLMS])

        if kind == "continuous":
            stat, p = stats.friedmanchisquare(*matrix.T)
            test_name = "Friedman   "
        else:
            stat, p = cochrans_q(matrix)
            test_name = "Cochran's Q"

        sig = (p is not None) and not np.isnan(p) and (p < ALPHA)
        underline_results[(metric, strategy)] = (stat, p, sig)
        marker = " => UNDERLINE" if sig else ""
        print(f"  {strategy:<12}  {test_name}: stat={fmt_stat(stat)}, p={fmt_p(p)}{marker}")

# ---------------------------------------------------------------------------
# 3. Summary: QVTo column values with significance annotations
# ---------------------------------------------------------------------------
print("\n" + "=" * 65)
print("QVTo COLUMN SUMMARY  (GPT | Gemini | Claude)")
print("  [ul] = triple underlined in LaTeX")
print("  *    = significantly better than Baseline")
print("=" * 65)

all_strategies = ["Baseline"] + STRATEGIES

for metric, label, kind, _ in METRICS_STAR:
    print(f"\n{label}:")
    for strategy in all_strategies:
        vals, markers = [], []
        for llm in LLMS:
            v   = get_vals(strategy, llm, metric).mean()
            sig = star_results.get((metric, strategy, llm), (None, False))[1]
            vals.append(v)
            markers.append("*" if sig else " ")
        ul     = underline_results.get((metric, strategy), (None, None, False))[2]
        prefix = "[ul]" if ul else "    "
        cells  = "  ".join(f"{v:.4f}{m}" for v, m in zip(vals, markers))
        print(f"  {prefix} {strategy:<12}  {cells}")

# ---------------------------------------------------------------------------
# 4. Export CSV results
# ---------------------------------------------------------------------------
from pathlib import Path
import pandas as pd

output_dir = Path(r"C:\Users\10239\OneDrive\Desktop\QVT-O siginificanttest\outputs")
output_dir.mkdir(exist_ok=True)

# --- 4a. Star test results ---
star_rows = []
for metric, label, kind, higher_better in METRICS_STAR:
    test_type = "Wilcoxon (one-sided)" if kind == "continuous" else "McNemar (one-sided)"
    for strategy in STRATEGIES:
        for llm in LLMS:
            p, sig = star_results.get((metric, strategy, llm), (np.nan, False))
            star_rows.append({
                "Language":    "QVT-O",
                "TestType":    "Star",
                "StatTest":    test_type,
                "Metric":      label,
                "Strategy":    strategy,
                "LLM":         llm,
                "p_value":     round(p, 6) if not np.isnan(p) else "NaN",
                "Significant": "Yes" if sig else "No",
            })

# --- 4b. Underline test results ---
ul_rows = []
for metric, label, kind in METRICS_UL:
    test_type = "Friedman" if kind == "continuous" else "Cochran's Q"
    for strategy in ["Baseline"] + STRATEGIES:
        stat, p, sig = underline_results.get((metric, strategy), (np.nan, np.nan, False))
        ul_rows.append({
            "Language":    "QVT-O",
            "TestType":    "Underline",
            "StatTest":    test_type,
            "Metric":      label,
            "Strategy":    strategy,
            "LLM":         "All",
            "stat_value":  round(float(stat), 6) if not np.isnan(stat) else "NaN",
            "p_value":     round(float(p), 6) if not np.isnan(p) else "NaN",
            "Significant": "Yes" if sig else "No",
        })

# --- 4c. Summary values table ---
summary_rows = []
for metric, label, kind, _ in METRICS_STAR:
    for strategy in ["Baseline"] + STRATEGIES:
        ul_sig = underline_results.get((metric, strategy), (None, None, False))[2]
        for llm in LLMS:
            v      = np.nanmean(get_vals(strategy, llm, metric))
            _, star_s = star_results.get((metric, strategy, llm), (None, False))
            summary_rows.append({
                "Language":  "QVT-O",
                "Metric":    label,
                "Strategy":  strategy,
                "LLM":       llm,
                "Mean":      round(v, 4),
                "Star":      "Yes" if star_s else "No",
                "Underline": "Yes" if ul_sig else "No",
            })

star_df    = pd.DataFrame(star_rows)
ul_df      = pd.DataFrame(ul_rows)
summary_df = pd.DataFrame(summary_rows)

star_df.to_csv(output_dir / "qvto_star_tests.csv", index=False)
ul_df.to_csv(output_dir / "qvto_underline_tests.csv", index=False)
summary_df.to_csv(output_dir / "qvto_summary_with_sig.csv", index=False)

# Unified significance_pvalues format
pvalue_rows = []
for r in star_rows:
    pvalue_rows.append({
        "LLM":         r["LLM"],
        "metric":      r["Metric"],
        "baseline":    "Baseline",
        "strategy":    r["Strategy"],
        "test":        r["StatTest"],
        "p_value":     r["p_value"],
        "significant": r["Significant"] == "Yes",
    })
pd.DataFrame(pvalue_rows).to_csv(output_dir / "significance_pvalues.csv", index=False)

print(f"\nCSV results saved to: {output_dir}")
print(f"  qvto_star_tests.csv       — star (*) p-values per LLM x strategy")
print(f"  qvto_underline_tests.csv  — underline p-values per strategy (across LLMs)")
print(f"  qvto_summary_with_sig.csv — mean values with significance flags")
print(f"  significance_pvalues.csv  — unified p-value table")
