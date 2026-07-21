"""
Statistical significance tests for LLM comparison in Reactions evaluation.

For continuous metrics (ErrorsPerLineOfCode / PPL_s, ChrF similarity):
  -> Friedman test across LLMs (within each strategy, tasks are blocks)

For binary metrics (Parsed, Parsed & Tests Passed):
  -> Cochran's Q test across LLMs

Gray-shading rule: if p < 0.05, the triple (GPT, Gemini, Claude) is gray-shaded.
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.stats import friedmanchisquare


# ── Load data ─────────────────────────────────────────────────────────────────
parsed_df  = pd.read_csv("parsed_rate_report (1).csv")
chrf_df    = pd.read_csv("chrf_similarity_report (1).csv")
test_df    = pd.read_csv("test_matrix_report (1).csv")

STRATEGY_MAP = {
    "only_prompt":                    "Baseline",
    "few_shot":                       "Few-Shot (FS)",
    "grammar":                        "Grammar (GR)",
    "few_shots_AND_grammar":          "FS + GR",
    "few_shots_AND_grammar_AND_helper": "FS + GR + HM",
}

LLM_ORDER = ["gpt-5", "gemini-2-5-pro", "claude-sonnet-4"]


# ── Helper: Friedman test ─────────────────────────────────────────────────────
def friedman_p(df, strategy, metric, llm_col="LLM", task_col=None):
    """
    Friedman test: tasks are blocks, LLMs are treatments.
    Returns p-value (or NaN if not enough data).
    """
    sub = df[df["Strategy"] == strategy]
    groups = []
    for llm in LLM_ORDER:
        g = sub[sub[llm_col] == llm][metric].values
        groups.append(g)

    # All groups must have the same length (matched tasks)
    lengths = [len(g) for g in groups]
    if len(set(lengths)) != 1 or lengths[0] < 2:
        return float("nan")

    _, p = friedmanchisquare(*groups)
    return p


# ── Helper: Cochran's Q test ──────────────────────────────────────────────────
def cochran_q_p(matrix):
    """
    Cochran's Q test on a (blocks × treatments) binary matrix.
    Returns p-value.
    """
    n, k = matrix.shape  # n = blocks (tasks), k = treatments (LLMs)
    L = matrix.sum(axis=1)   # row sums
    C = matrix.sum(axis=0)   # col sums
    total = matrix.sum()

    Q_num = k * (k - 1) * np.sum(C**2) - k * (k - 1) * (total**2 / k)
    Q_den = k * total - np.sum(L**2)

    if Q_den == 0:
        return float("nan")
    Q = Q_num / Q_den
    p = 1 - stats.chi2.cdf(Q, df=k - 1)
    return p


def cochran_p(df, strategy, binary_col, llm_col="LLM"):
    """Build the blocks×treatments binary matrix and run Cochran's Q."""
    sub = df[df["Strategy"] == strategy]

    # Identify the task column
    if "File" in df.columns:
        task_col = "File"
    elif "ReactionFile" in df.columns:
        task_col = "ReactionFile"
        # Normalise to task name
        sub = sub.copy()
        sub["task"] = sub[task_col].str.extract(r"/([^/]+)\.reactions$")[0]
        task_col = "task"
    else:
        return float("nan")

    pivot = sub.pivot_table(index=task_col, columns=llm_col, values=binary_col, aggfunc="first")
    pivot = pivot[LLM_ORDER].dropna()

    if pivot.shape[0] < 2:
        return float("nan")

    return cochran_q_p(pivot.values)


# ── 1. PPL_s  (ErrorsPerLineOfCode) — Friedman ───────────────────────────────
print("=" * 60)
print("1. PPL_s (Errors per LoC) — Friedman test")
print("=" * 60)
print(f"{'Strategy':<25} {'GPT mean':>10} {'Gem mean':>10} {'Cla mean':>10}  {'p-value':>10}  sig?")
print("-" * 75)

for strat_key, strat_label in STRATEGY_MAP.items():
    sub = parsed_df[parsed_df["Strategy"] == strat_key]
    means = {}
    for llm in LLM_ORDER:
        means[llm] = sub[sub["LLM"] == llm]["ErrorsPerLineOfCode"].mean()

    p = friedman_p(parsed_df, strat_key, "ErrorsPerLineOfCode")
    sig = "*** YES ***" if (not np.isnan(p) and p < 0.05) else "no"
    print(f"{strat_label:<25} {means['gpt-5']:>10.4f} {means['gemini-2-5-pro']:>10.4f} "
          f"{means['claude-sonnet-4']:>10.4f}  {p:>10.4f}  {sig}")


# ── 2. ChrF similarity — Friedman ────────────────────────────────────────────
print()
print("=" * 60)
print("2. ChrF Similarity — Friedman test")
print("=" * 60)

# Normalise strategy names in chrf_df if needed
chrf_strat_vals = chrf_df["Strategy"].unique()
print(f"   (strategies in file: {list(chrf_strat_vals)})")
print(f"{'Strategy':<25} {'GPT mean':>10} {'Gem mean':>10} {'Cla mean':>10}  {'p-value':>10}  sig?")
print("-" * 75)

for strat_key, strat_label in STRATEGY_MAP.items():
    sub = chrf_df[chrf_df["Strategy"] == strat_key]
    if sub.empty:
        print(f"{strat_label:<25}  (no data)")
        continue
    means = {}
    for llm in LLM_ORDER:
        means[llm] = sub[sub["LLM"] == llm]["Score"].mean()

    p = friedman_p(chrf_df, strat_key, "Score", task_col="File")
    sig = "*** YES ***" if (not np.isnan(p) and p < 0.05) else "no"
    print(f"{strat_label:<25} {means['gpt-5']:>10.4f} {means['gemini-2-5-pro']:>10.4f} "
          f"{means['claude-sonnet-4']:>10.4f}  {p:>10.4f}  {sig}")


# ── 3. Parsability (binary) — Cochran's Q ────────────────────────────────────
print()
print("=" * 60)
print("3. Parsability (Parsed) — Cochran's Q test")
print("=" * 60)

parsed_df2 = parsed_df.copy()
parsed_df2["ParsedBin"] = parsed_df2["Parsed"].map({"True": 1, "False": 0, True: 1, False: 0})

print(f"{'Strategy':<25} {'GPT rate':>10} {'Gem rate':>10} {'Cla rate':>10}  {'p-value':>10}  sig?")
print("-" * 75)

for strat_key, strat_label in STRATEGY_MAP.items():
    sub = parsed_df2[parsed_df2["Strategy"] == strat_key]
    rates = {}
    for llm in LLM_ORDER:
        rates[llm] = sub[sub["LLM"] == llm]["ParsedBin"].mean()

    p = cochran_p(parsed_df2, strat_key, "ParsedBin")
    sig = "*** YES ***" if (not np.isnan(p) and p < 0.05) else "no"
    print(f"{strat_label:<25} {rates['gpt-5']:>10.4f} {rates['gemini-2-5-pro']:>10.4f} "
          f"{rates['claude-sonnet-4']:>10.4f}  {p:>10.4f}  {sig}")


# ── 4. Parsed & Tests Passed (binary) — Cochran's Q ──────────────────────────
print()
print("=" * 60)
print("4. Parsable & Tests Passed — Cochran's Q test")
print("=" * 60)

# Merge parsed + test results
# test_df has ExitCode (0 = ran) and Passed column
test_df2 = test_df.copy()
test_df2["AllPassed"] = ((test_df2["ExitCode"] == 0) &
                          (test_df2["Tests"] == test_df2["Passed"])).astype(int)

print(f"{'Strategy':<25} {'GPT rate':>10} {'Gem rate':>10} {'Cla rate':>10}  {'p-value':>10}  sig?")
print("-" * 75)

for strat_key, strat_label in STRATEGY_MAP.items():
    sub = test_df2[test_df2["Strategy"] == strat_key]
    if sub.empty:
        print(f"{strat_label:<25}  (no data)")
        continue
    rates = {}
    for llm in LLM_ORDER:
        rates[llm] = sub[sub["LLM"] == llm]["AllPassed"].mean()

    # Build pivot for Cochran's Q
    sub2 = sub.copy()
    pivot = sub2.pivot_table(index="Task", columns="LLM", values="AllPassed", aggfunc="first")
    pivot = pivot[[c for c in LLM_ORDER if c in pivot.columns]].dropna()
    if pivot.shape[0] < 2 or pivot.shape[1] < 3:
        p = float("nan")
    else:
        p = cochran_q_p(pivot.values)

    sig = "*** YES ***" if (not np.isnan(p) and p < 0.05) else "no"
    print(f"{strat_label:<25} {rates.get('gpt-5', float('nan')):>10.4f} "
          f"{rates.get('gemini-2-5-pro', float('nan')):>10.4f} "
          f"{rates.get('claude-sonnet-4', float('nan')):>10.4f}  {p:>10.4f}  {sig}")

print()
print("Done. Gray-shade a triple if p < 0.05.")

# ── Export all results to CSV ─────────────────────────────────────────────────
records = []

# 1. PPL_s (ErrorsPerLineOfCode) — Friedman
for strat_key, strat_label in STRATEGY_MAP.items():
    sub = parsed_df[parsed_df["Strategy"] == strat_key]
    means = {llm: sub[sub["LLM"] == llm]["ErrorsPerLineOfCode"].mean() for llm in LLM_ORDER}
    p = friedman_p(parsed_df, strat_key, "ErrorsPerLineOfCode")
    records.append({
        "Metric": "PPL_s (ErrorsPerLoC)",
        "Test": "Friedman",
        "Language": "Reactions",
        "Strategy": strat_label,
        "GPT_mean": round(means["gpt-5"], 4),
        "Gemini_mean": round(means["gemini-2-5-pro"], 4),
        "Claude_mean": round(means["claude-sonnet-4"], 4),
        "p_value": round(p, 4) if not np.isnan(p) else "NaN",
        "Significant": "Yes" if (not np.isnan(p) and p < 0.05) else "No",
    })

# 2. ChrF — Friedman
for strat_key, strat_label in STRATEGY_MAP.items():
    sub = chrf_df[chrf_df["Strategy"] == strat_key]
    if sub.empty:
        continue
    means = {llm: sub[sub["LLM"] == llm]["Score"].mean() for llm in LLM_ORDER}
    p = friedman_p(chrf_df, strat_key, "Score")
    records.append({
        "Metric": "ChrF",
        "Test": "Friedman",
        "Language": "Reactions",
        "Strategy": strat_label,
        "GPT_mean": round(means["gpt-5"], 4),
        "Gemini_mean": round(means["gemini-2-5-pro"], 4),
        "Claude_mean": round(means["claude-sonnet-4"], 4),
        "p_value": round(p, 4) if not np.isnan(p) else "NaN",
        "Significant": "Yes" if (not np.isnan(p) and p < 0.05) else "No",
    })

# 3. Parsability — Cochran's Q
for strat_key, strat_label in STRATEGY_MAP.items():
    sub = parsed_df2[parsed_df2["Strategy"] == strat_key]
    rates = {llm: sub[sub["LLM"] == llm]["ParsedBin"].mean() for llm in LLM_ORDER}
    p = cochran_p(parsed_df2, strat_key, "ParsedBin")
    records.append({
        "Metric": "Parsability",
        "Test": "Cochran's Q",
        "Language": "Reactions",
        "Strategy": strat_label,
        "GPT_mean": round(rates["gpt-5"], 4),
        "Gemini_mean": round(rates["gemini-2-5-pro"], 4),
        "Claude_mean": round(rates["claude-sonnet-4"], 4),
        "p_value": round(p, 4) if not np.isnan(p) else "NaN",
        "Significant": "Yes" if (not np.isnan(p) and p < 0.05) else "No",
    })

# 4. Parsed & Tests Passed — Cochran's Q
for strat_key, strat_label in STRATEGY_MAP.items():
    sub = test_df2[test_df2["Strategy"] == strat_key]
    if sub.empty:
        continue
    rates = {llm: sub[sub["LLM"] == llm]["AllPassed"].mean() for llm in LLM_ORDER}
    pivot = sub.pivot_table(index="Task", columns="LLM", values="AllPassed", aggfunc="first")
    pivot = pivot[[c for c in LLM_ORDER if c in pivot.columns]].dropna()
    p = cochran_q_p(pivot.values) if (pivot.shape[0] >= 2 and pivot.shape[1] == 3) else float("nan")
    records.append({
        "Metric": "Parsed & Tests Passed",
        "Test": "Cochran's Q",
        "Language": "Reactions",
        "Strategy": strat_label,
        "GPT_mean": round(rates.get("gpt-5", float("nan")), 4),
        "Gemini_mean": round(rates.get("gemini-2-5-pro", float("nan")), 4),
        "Claude_mean": round(rates.get("claude-sonnet-4", float("nan")), 4),
        "p_value": round(p, 4) if not np.isnan(p) else "NaN",
        "Significant": "Yes" if (not np.isnan(p) and p < 0.05) else "No",
    })

results_df = pd.DataFrame(records)
output_path = "significance_results.csv"
results_df.to_csv(output_path, index=False)
print(f"\nResults saved to: {output_path}")
