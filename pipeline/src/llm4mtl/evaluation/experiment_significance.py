"""Experiment-level significance over paired binary outcomes.

Significance is an experiment-level concern (baseline vs an ablation variant across
matched items), never a per-run one. The per-language scripts under
``evaluation/{atl,etl,qvto,reactions}/`` remain the reference implementation for the
existing thesis CSVs; this is the run-store-native home for new experiments.
"""

from __future__ import annotations

from typing import Any


def mcnemar(baseline: list[bool], variant: list[bool]) -> dict[str, Any]:
    """Run the exact McNemar test for paired binary outcomes (``True`` = pass)."""
    if len(baseline) != len(variant):
        raise ValueError("paired samples must have equal length")

    contingency_table = [[0, 0], [0, 0]]
    for baseline_passed, variant_passed in zip(baseline, variant):
        baseline_index = 0 if baseline_passed else 1
        variant_index = 0 if variant_passed else 1
        contingency_table[baseline_index][variant_index] += 1

    both_pass, baseline_only = contingency_table[0]
    variant_only, both_fail = contingency_table[1]

    p_value = _exact_p(baseline_only, variant_only)
    try:  # prefer statsmodels when available, but never require it
        from statsmodels.stats.contingency_tables import mcnemar as _sm_mcnemar

        p_value = float(_sm_mcnemar(contingency_table, exact=True).pvalue)
    except Exception:
        pass

    return {
        "schema_version": "1.0",
        "test": "mcnemar_exact",
        "both_pass": both_pass,
        "baseline_only": baseline_only,
        "variant_only": variant_only,
        "both_fail": both_fail,
        "p_value": p_value,
    }


def _exact_p(baseline_only: int, variant_only: int) -> float:
    """Return the dependency-free, two-sided exact discordant-pair p-value."""
    from math import comb

    n = baseline_only + variant_only
    if n == 0:
        return 1.0
    k = min(baseline_only, variant_only)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)
