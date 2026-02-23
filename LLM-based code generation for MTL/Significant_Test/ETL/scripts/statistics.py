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
        return (np.nan, len(differences), f"Insufficient valid samples (only {len(non_zero_diffs)} non-zero differences)")
    
    try:
        # Perform Wilcoxon test (two-tailed)
        statistic, p_value = wilcoxon(strategy_values, baseline_values, alternative='two-sided')
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
    
    # Build 2x2 contingency table
    # a: baseline=True, strategy=True
    # b: baseline=True, strategy=False
    # c: baseline=False, strategy=True
    # d: baseline=False, strategy=False
    a = b = c = d = 0
    
    for bl, st in zip(baseline_values, strategy_values):
        bl_bool = bool(bl) if not pd.isna(bl) else False
        st_bool = bool(st) if not pd.isna(st) else False
        
        if bl_bool and st_bool:
            a += 1
        elif bl_bool and not st_bool:
            b += 1
        elif not bl_bool and st_bool:
            c += 1
        else:
            d += 1
    
    # If b+c=0 (no changes), p_value = 1.0
    if b + c == 0:
        return (1.0, len(baseline_values), "No changes (b+c=0)")
    
    try:
        # Build contingency table (McNemar only cares about discordant pairs)
        # Use statsmodels mcnemar function
        table = [[a, b], [c, d]]
        result = mcnemar(table, exact=True, correction=False)
        p_value = result.pvalue
        return (p_value, len(baseline_values), None)
    except Exception as e:
        return (np.nan, len(baseline_values), f"Test failed: {str(e)}")

