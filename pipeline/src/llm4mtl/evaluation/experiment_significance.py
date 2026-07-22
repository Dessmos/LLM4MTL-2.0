"""Experiment-level significance over paired binary outcomes.

Significance is an experiment-level concern (baseline vs an ablation variant across
matched items), never a per-run one. The per-language scripts under
``evaluation/{atl,etl,qvto,reactions}/`` remain the reference implementation for the
existing thesis CSVs; this is the run-store-native home for new experiments.
"""

from __future__ import annotations

from typing import Any


def mcnemar(baseline: list[bool], variant: list[bool]) -> dict[str, Any]:
    """Exact McNemar test for two paired binary outcome vectors (True = pass)."""
    if len(baseline) != len(variant):
        raise ValueError("paired samples must have equal length")

    both_pass = sum(1 for a, b in zip(baseline, variant) if a and b)
    baseline_only = sum(1 for a, b in zip(baseline, variant) if a and not b)
    variant_only = sum(1 for a, b in zip(baseline, variant) if not a and b)
    both_fail = sum(1 for a, b in zip(baseline, variant) if not a and not b)

    p_value = _exact_p(baseline_only, variant_only)
    try:  # prefer statsmodels when available, but never require it
        from statsmodels.stats.contingency_tables import mcnemar as _sm_mcnemar

        p_value = float(_sm_mcnemar([[both_pass, baseline_only], [variant_only, both_fail]], exact=True).pvalue)
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
    """Two-sided exact binomial p-value on the discordant pairs (dependency-free)."""
    from math import comb

    n = baseline_only + variant_only
    if n == 0:
        return 1.0
    k = min(baseline_only, variant_only)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)
