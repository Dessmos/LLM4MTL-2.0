"""
Data processing functions for loading, cleaning, and preparing data.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import os

# Add scripts directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from file_utils import find_ground_truth_dir, build_file_to_loc_mapping, match_file_to_ground_truth


def convert_to_bool(val):
    """
    Convert value to boolean, handling various input types.
    
    Args:
        val: Value to convert (can be bool, str, int, etc.)
        
    Returns:
        Boolean value or np.nan if cannot convert
    """
    if pd.isna(val):
        return np.nan
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val_lower = val.strip().lower()
        if val_lower in ['true', '1', 'yes']:
            return True
        elif val_lower in ['false', '0', 'no']:
            return False
        else:
            return np.nan
    # Try to convert to boolean
    try:
        return bool(val)
    except:
        return np.nan


def convert_parsed_to_bool(val):
    """
    Convert Parsed value to boolean.
    
    Args:
        val: Value to convert
        
    Returns:
        Boolean value (defaults to False if cannot convert)
    """
    if pd.isna(val):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ['true', '1', 'yes']
    return bool(val)


def load_and_prepare_data(raw_csv_path, gt_dir=None):
    """
    Load CSV data and prepare it for significance testing.
    
    Args:
        raw_csv_path: Path to input CSV file
        gt_dir: Ground truth directory (None means auto-detect)
        
    Returns:
        tuple: (dataframe, ground_truth_dir)
    """
    # Read input data
    print(f"Reading input data: {raw_csv_path}")
    try:
        df = pd.read_csv(raw_csv_path)
    except Exception as e:
        raise ValueError(f"Cannot read CSV file: {e}")
    
    # Check required columns
    required_cols = ['LLM', 'Strategy', 'File', 'Parsed', 'ProblemCount', 'CHRF_Score']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV file missing required columns: {missing_cols}")
    
    # Check test_pass column, try to merge from other files if missing or set to NaN
    if 'test_pass' not in df.columns:
        print("Warning: CSV file missing test_pass column, trying to find from other locations...")
        # Try to find from ATL_Tests_New directory
        repo_root = Path(raw_csv_path).resolve().parent.parent
        possible_test_files = [
            repo_root / 'ATL_Tests_New' / 'atl_test_results.csv',
            repo_root / 'ATLParser' / 'atl_test_results.csv',
        ]
        
        test_pass_merged = False
        for test_file in possible_test_files:
            if test_file.exists():
                print(f"  Trying to merge test_pass data from {test_file}...")
                try:
                    test_df = pd.read_csv(test_file)
                    if 'test_pass' in test_df.columns and 'LLM' in test_df.columns and 'Strategy' in test_df.columns and 'File' in test_df.columns:
                        # Merge test_pass data
                        test_pass_df = test_df[['LLM', 'Strategy', 'File', 'test_pass']].copy()
                        df = df.merge(test_pass_df, on=['LLM', 'Strategy', 'File'], how='left', suffixes=('', '_merged'))
                        if 'test_pass_merged' in df.columns:
                            df['test_pass'] = df['test_pass_merged']
                            df = df.drop(columns=['test_pass_merged'])
                        print(f"  Successfully merged {df['test_pass'].notna().sum()} test_pass records")
                        test_pass_merged = True
                        break
                except Exception as e:
                    print(f"  Cannot read from {test_file}: {e}")
                    continue
        
        if not test_pass_merged:
            print("  No file containing test_pass found, setting to NaN")
            df['test_pass'] = np.nan
    else:
        df['test_pass'] = df['test_pass'].apply(convert_to_bool)
        print(f"test_pass data type: {df['test_pass'].dtype}")
        print(f"test_pass non-null count: {df['test_pass'].notna().sum()}/{len(df)}")
        print(f"test_pass=True count: {(df['test_pass'] == True).sum()}")
        print(f"test_pass=False count: {(df['test_pass'] == False).sum()}")
    
    # Convert Parsed to boolean
    df['Parsed'] = df['Parsed'].apply(convert_parsed_to_bool)
    
    # Find ground truth directory
    if gt_dir is None or gt_dir == 'auto':
        repo_root = Path(raw_csv_path).resolve().parent.parent
        gt_dir = find_ground_truth_dir(repo_root)
        if gt_dir is None:
            raise ValueError("Cannot automatically find ground truth directory. Please use --gt_dir parameter to specify the ground truth ATL file directory")
        print(f"Auto-found ground truth directory: {gt_dir}")
    
    # Build File -> reference_LOC mapping
    print("Calculating reference LOC...")
    file_to_loc = build_file_to_loc_mapping(gt_dir)
    print(f"Found {len(file_to_loc)} ground truth files")
    
    # Match reference_LOC for each File
    df['reference_LOC'] = df['File'].apply(lambda x: match_file_to_ground_truth(x, file_to_loc))
    
    # Check for unmatched Files
    unmatched_files = df[df['reference_LOC'].isna()]['File'].unique()
    if len(unmatched_files) > 0:
        print(f"\nError: The following Files cannot be matched to ground truth files:")
        for f in sorted(unmatched_files):
            print(f"  - {f}")
        print(f"\nAvailable ground truth files:")
        for f in sorted(file_to_loc.keys()):
            print(f"  - {f}")
        raise ValueError("Some Files cannot be matched to ground truth files")
    
    # Calculate errors_per_LOC
    df['errors_per_LOC'] = df['ProblemCount'] / df['reference_LOC']
    
    return df, gt_dir


def add_significance_markers(summary_df, results_df):
    """
    Add significance markers (*) to summary table based on test results.
    
    Args:
        summary_df: Summary dataframe
        results_df: Results dataframe with significance test results
        
    Returns:
        Summary dataframe with significance markers
    """
    # Create significance marker dictionary
    sig_dict = {}
    for _, row in results_df.iterrows():
        if row['significant']:
            key = (row['LLM'], row['strategy'], row['metric'])
            sig_dict[key] = True
    
    # Add significance marker function
    def add_sig_marker(value, llm, strategy, metric):
        if pd.isna(value):
            return value
        key = (llm, strategy, metric)
        if sig_dict.get(key, False):
            return f"{value:.3f}*" if isinstance(value, float) else f"{value}*"
        return f"{value:.3f}" if isinstance(value, float) else str(value)
    
    # Add markers according to summary table column names
    summary_with_sig = summary_df.copy()
    
    # Process CHRF_Score
    if 'CHRF_Score' in summary_with_sig.columns:
        summary_with_sig['CHRF_Score'] = summary_with_sig.apply(
            lambda row: add_sig_marker(row['CHRF_Score'], row['LLM'], row['Strategy'], 'CHRF_Score'),
            axis=1
        )
    
    # Process errors_per_LOC
    if 'errors_per_LOC' in summary_with_sig.columns:
        summary_with_sig['errors_per_LOC'] = summary_with_sig.apply(
            lambda row: add_sig_marker(row['errors_per_LOC'], row['LLM'], row['Strategy'], 'errors_per_LOC'),
            axis=1
        )
    
    # Process Parsed-related columns
    parsed_cols = [col for col in summary_with_sig.columns if 'Parsed' in col]
    for col in parsed_cols:
        summary_with_sig[col] = summary_with_sig.apply(
            lambda row: add_sig_marker(row[col], row['LLM'], row['Strategy'], 'Parsed'),
            axis=1
        )
    
    # Process test_pass-related columns
    test_pass_cols = [col for col in summary_with_sig.columns if 'test_pass' in col.lower()]
    for col in test_pass_cols:
        summary_with_sig[col] = summary_with_sig.apply(
            lambda row: add_sig_marker(row[col], row['LLM'], row['Strategy'], 'test_pass'),
            axis=1
        )
    
    return summary_with_sig

