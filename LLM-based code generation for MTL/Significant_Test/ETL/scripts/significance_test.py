#!/usr/bin/env python3
"""
Significance Test Statistical Pipeline

This script performs paired significance tests on ATL parsing results, comparing different strategies against the baseline.

Methodology:
1. Baseline: Fixed as 'only_prompt' strategy
2. LOC Definition: Count physical lines from ground truth ATL files, excluding empty lines and pure comment lines
   - ATL single-line comments start with --
   - Check if a line is a comment after stripping leading whitespace
3. Paired Design: Separate by LLM, each strategy is paired with baseline on the same File
4. Statistical Tests:
   - Continuous metrics (CHRF_Score, errors_per_LOC): Wilcoxon signed-rank test (two-tailed)
     Rationale: Paired design, continuous data, non-parametric test suitable for small samples
   - Binary metrics (Parsed, test_pass): McNemar exact test (two-tailed)
     Rationale: Paired design, binary data, McNemar test is specifically designed for paired binary data

Input:
- atl_parser_chrf_results.csv: Contains LLM, Strategy, File, Parsed, ProblemCount, CHRF_Score, test_pass

Output:
- outputs/significance_pvalues.csv: Significance test p-value results
- outputs/summary_with_sig.csv: Summary table with significance markers
"""

import os
import sys
import argparse
import pandas as pd
import numpy as np
from pathlib import Path
import warnings

from file_utils import find_ground_truth_dir
from statistics import perform_wilcoxon_test, perform_mcnemar_test
from data_processing import load_and_prepare_data, add_significance_markers

warnings.filterwarnings('ignore')


def run_significance_tests(df, baseline_strategy='only_prompt', strategies_to_test=None):
    """
    Run significance tests for all LLM-strategy combinations.
    
    Args:
        df: Prepared dataframe with all required columns
        baseline_strategy: Baseline strategy name
        strategies_to_test: List of strategies to test against baseline
        
    Returns:
        DataFrame with test results
    """
    if strategies_to_test is None:
        strategies_to_test = ['few_shot', 'grammar', 'few_shots_AND_grammar']
    
    results = []
    
    for llm in df['LLM'].unique():
        print(f"  Processing LLM: {llm}")
        df_llm = df[df['LLM'] == llm]
        
        # Get baseline data
        baseline_df = df_llm[df_llm['Strategy'] == baseline_strategy].copy()
        if len(baseline_df) == 0:
            print(f"    Warning: {llm} has no baseline data, skipping")
            continue
        
        for strategy in strategies_to_test:
            strategy_df = df_llm[df_llm['Strategy'] == strategy].copy()
            if len(strategy_df) == 0:
                continue
            
            # Pair by File
            merged = pd.merge(
                baseline_df[['File', 'CHRF_Score', 'Parsed', 'test_pass', 'errors_per_LOC']],
                strategy_df[['File', 'CHRF_Score', 'Parsed', 'test_pass', 'errors_per_LOC']],
                on='File',
                suffixes=('_baseline', '_strategy')
            )
            
            if len(merged) == 0:
                continue
            
            # Continuous metric: CHRF_Score
            baseline_chrf = merged['CHRF_Score_baseline'].values
            strategy_chrf = merged['CHRF_Score_strategy'].values
            p_chrf, n_chrf, reason_chrf = perform_wilcoxon_test(baseline_chrf, strategy_chrf)
            results.append({
                'LLM': llm,
                'metric': 'CHRF_Score',
                'baseline': baseline_strategy,
                'strategy': strategy,
                'n_pairs': n_chrf,
                'test': 'Wilcoxon',
                'p_value': p_chrf,
                'significant': p_chrf < 0.05 if not pd.isna(p_chrf) else False,
                'reason': reason_chrf if reason_chrf else ''
            })
            
            # Continuous metric: errors_per_LOC
            baseline_errors = merged['errors_per_LOC_baseline'].values
            strategy_errors = merged['errors_per_LOC_strategy'].values
            p_errors, n_errors, reason_errors = perform_wilcoxon_test(baseline_errors, strategy_errors)
            results.append({
                'LLM': llm,
                'metric': 'errors_per_LOC',
                'baseline': baseline_strategy,
                'strategy': strategy,
                'n_pairs': n_errors,
                'test': 'Wilcoxon',
                'p_value': p_errors,
                'significant': p_errors < 0.05 if not pd.isna(p_errors) else False,
                'reason': reason_errors if reason_errors else ''
            })
            
            # Binary metric: Parsed
            baseline_parsed = merged['Parsed_baseline'].values
            strategy_parsed = merged['Parsed_strategy'].values
            p_parsed, n_parsed, reason_parsed = perform_mcnemar_test(baseline_parsed, strategy_parsed)
            results.append({
                'LLM': llm,
                'metric': 'Parsed',
                'baseline': baseline_strategy,
                'strategy': strategy,
                'n_pairs': n_parsed,
                'test': 'McNemar',
                'p_value': p_parsed,
                'significant': p_parsed < 0.05 if not pd.isna(p_parsed) else False,
                'reason': reason_parsed if reason_parsed else ''
            })
            
            # Binary metric: test_pass
            baseline_test = merged['test_pass_baseline'].values
            strategy_test = merged['test_pass_strategy'].values
            
            # Debug info: print pairing matrix
            print(f"\n    [{llm} vs {strategy}] test_pass pairing matrix:")
            print(f"      Paired files: {len(merged)}")
            
            # Check for NaN values
            valid_mask = ~(pd.isna(baseline_test) | pd.isna(strategy_test))
            n_valid = valid_mask.sum()
            print(f"      Valid paired samples: {n_valid}/{len(merged)}")
            
            if n_valid > 0:
                baseline_test_valid = baseline_test[valid_mask]
                strategy_test_valid = strategy_test[valid_mask]
                
                # Build 2x2 matrix for display
                a = b = c = d = 0
                for bl, st in zip(baseline_test_valid, strategy_test_valid):
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
                
                print(f"      Pairing matrix (baseline x strategy):")
                print(f"        [True, True] = {a}")
                print(f"        [True, False] = {b}")
                print(f"        [False, True] = {c}")
                print(f"        [False, False] = {d}")
                print(f"        Discordant pairs (b+c) = {b + c}")
                
                p_test, n_test, reason_test = perform_mcnemar_test(baseline_test_valid, strategy_test_valid)
                p_value_str = f"{p_test:.6f}" if not pd.isna(p_test) else "NaN"
                print(f"      McNemar p_value = {p_value_str}")
            else:
                p_test, n_test, reason_test = (np.nan, 0, "All values are NaN")
                print(f"      Skipping McNemar test (no valid pairs)")
            results.append({
                'LLM': llm,
                'metric': 'test_pass',
                'baseline': baseline_strategy,
                'strategy': strategy,
                'n_pairs': n_test,
                'test': 'McNemar',
                'p_value': p_test,
                'significant': p_test < 0.05 if not pd.isna(p_test) else False,
                'reason': reason_test if reason_test else ''
            })
    
    return pd.DataFrame(results)


def generate_summary_table(df, summary_csv_path=None):
    """
    Generate or load summary table.
    
    Args:
        df: Prepared dataframe
        summary_csv_path: Optional path to existing summary CSV
        
    Returns:
        Summary dataframe
    """
    if summary_csv_path and os.path.exists(summary_csv_path):
        summary_df = pd.read_csv(summary_csv_path)
        print(f"Reading summary table from {summary_csv_path}")
        return summary_df
    else:
        # Aggregate to generate summary table
        print("Aggregating from raw data to generate summary table")
        summary_df = df.groupby(['LLM', 'Strategy']).agg({
            'CHRF_Score': 'mean',
            'Parsed': lambda x: (x == True).sum() / len(x) * 100,  # Percentage
            'test_pass': lambda x: (x == True).sum() / len(x) * 100 if x.notna().any() else np.nan,
            'errors_per_LOC': 'mean',
            'ProblemCount': 'sum',
            'File': 'count'  # Total count
        }).reset_index()
        summary_df.columns = ['LLM', 'Strategy', 'CHRF_Score', 'Parsed_Rate(%)', 'test_pass_Rate(%)', 
                             'errors_per_LOC', 'Total_Problems', 'Total']
        return summary_df


def main():
    parser = argparse.ArgumentParser(description='Perform significance tests on ATL parsing results')
    parser.add_argument('--raw_csv', type=str, required=True,
                        help='Input CSV file path (contains LLM, Strategy, File, Parsed, ProblemCount, CHRF_Score, test_pass)')
    parser.add_argument('--summary_csv', type=str, default=None,
                        help='Summary CSV file path (optional, used to generate summary_with_sig.csv)')
    parser.add_argument('--gt_dir', type=str, default='auto',
                        help='Ground truth ATL file directory (auto means auto-detect)')
    
    args = parser.parse_args()
    
    # Validate ground truth directory if specified
    if args.gt_dir != 'auto' and not os.path.isdir(args.gt_dir):
        print(f"Error: Specified ground truth directory does not exist: {args.gt_dir}")
        sys.exit(1)
    
    try:
        # Load and prepare data
        df, gt_dir = load_and_prepare_data(args.raw_csv, args.gt_dir)
        
        # Run significance tests
        print("\nPerforming significance tests...")
        results_df = run_significance_tests(df)
        
        # Save significance test results
        output_dir = Path('outputs')
        output_dir.mkdir(exist_ok=True)
        
        pvalues_file = output_dir / 'significance_pvalues.csv'
        results_df.to_csv(pvalues_file, index=False)
        print(f"\nSignificance test results saved to: {pvalues_file}")
        
        # Generate summary table with significance markers
        print("\nGenerating summary table with significance markers...")
        summary_df = generate_summary_table(df, args.summary_csv)
        summary_with_sig = add_significance_markers(summary_df, results_df)
        
        summary_file = output_dir / 'summary_with_sig.csv'
        summary_with_sig.to_csv(summary_file, index=False)
        print(f"Summary table with significance markers saved to: {summary_file}")
        
        # Output statistics
        print("\n=== Test Results Statistics ===")
        print(f"Total tests: {len(results_df)}")
        print(f"Significant results (p < 0.05): {results_df['significant'].sum()}")
        print(f"Results with uncalculable p-values: {results_df['p_value'].isna().sum()}")
        
        if results_df['p_value'].isna().any():
            print("\nReasons for uncalculable p-values:")
            na_results = results_df[results_df['p_value'].isna()]
            for reason in na_results['reason'].unique():
                if reason:
                    count = (na_results['reason'] == reason).sum()
                    print(f"  - {reason}: {count} times")
                    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
