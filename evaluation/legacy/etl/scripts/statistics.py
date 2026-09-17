"""
Statistical test functions for significance testing.
"""

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon
from statsmodels.stats.contingency_tables import mcnemar


def perform_wilcoxon_test(baseline_values, strategy_values):
    """
    Perform Wilcoxon signed-rank test

    Args:
        baseline_values: List of values for baseline strategy
        strategy_values: List of values for strategy to compare

    Returns:
        (p_value, n_pairs, reason)
    """
    # Ensure same length
    assert len(baseline_values) == len(strategy_values)

    # Calculate differences
    differences = [s - b for b, s in zip(baseline_values, strategy_values)]

    # Check if all differences are zero
    if all(d == 0 for d in differences):
        return (np.nan, len(differences), "All differences are zero")

    # Check valid sample size (non-zero differences)
    non_zero_diffs = [d for d in differences if d != 0]
    if len(non_zero_diffs) < 2:
        return (
            np.nan,
            len(differences),
            f"Insufficient valid samples (only {len(non_zero_diffs)} non-zero differences)",
        )

    try:
        # Perform Wilcoxon test (two-tailed)
        statistic, p_value = wilcoxon(
            strategy_values, baseline_values, alternative="two-sided"
        )
        return (p_value, len(differences), None)
    except Exception as e:
        return (np.nan, len(differences), f"Test failed: {str(e)}")


def perform_mcnemar_test(baseline_values, strategy_values):
    """
    Perform McNemar exact test

    Args:
        baseline_values: List of boolean values for baseline strategy
        strategy_values: List of boolean values for strategy to compare

    Returns:
        (p_value, n_pairs, reason)
    """
    # Ensure same length
    assert len(baseline_values) == len(strategy_values)

    # Rows represent baseline True/False; columns represent strategy True/False.
    table = [[0, 0], [0, 0]]

    for bl, st in zip(baseline_values, strategy_values):
        bl_bool = _boolean_value(bl)
        st_bool = _boolean_value(st)
        baseline_index = 0 if bl_bool else 1
        strategy_index = 0 if st_bool else 1
        table[baseline_index][strategy_index] += 1

    # If b+c=0 (no changes), p_value = 1.0
    discordant_pairs = table[0][1] + table[1][0]
    if discordant_pairs == 0:
        return (1.0, len(baseline_values), "No changes (b+c=0)")

    try:
        # Build contingency table (McNemar only cares about discordant pairs)
        # Use statsmodels mcnemar function
        result = mcnemar(table, exact=True, correction=False)
        p_value = result.pvalue
        return (p_value, len(baseline_values), None)
    except Exception as e:
        return (np.nan, len(baseline_values), f"Test failed: {str(e)}")


def _boolean_value(value):
    """Treat a missing observation as false, matching the legacy metric."""
    return bool(value) if not pd.isna(value) else False
