# Significance Test Statistical Pipeline

This module provides tools for performing paired significance tests on ATL parsing results, comparing different strategies against the baseline.

## Files

- `significance_test.py` - Main script for running significance tests
- `file_utils.py` - Utilities for finding ground truth files and counting LOC
- `statistics.py` - Statistical test functions (Wilcoxon, McNemar)
- `data_processing.py` - Data loading, cleaning, and preparation functions

## Usage

```bash
python scripts/significance_test.py \
  --raw_csv <path_to_csv> \
  --summary_csv <path_to_summary_csv> \
  --gt_dir auto
```

### Arguments

- `--raw_csv` (required): Input CSV file path containing LLM, Strategy, File, Parsed, ProblemCount, CHRF_Score, test_pass
- `--summary_csv` (optional): Summary CSV file path for generating summary_with_sig.csv
- `--gt_dir` (optional): Ground truth ATL file directory (default: 'auto' for auto-detection)

### Example

```bash
python scripts/significance_test.py \
  --raw_csv ATL_Tests_New/atl_test_results.csv \
  --summary_csv ATLParser/atl_summary_table.csv \
  --gt_dir auto
```

## Output

- `outputs/significance_pvalues.csv` - Significance test p-value results
- `outputs/summary_with_sig.csv` - Summary table with significance markers (* for p < 0.05)

## Methodology

1. **Baseline**: Fixed as 'only_prompt' strategy
2. **LOC Definition**: Count physical lines from ground truth ATL files, excluding empty lines and pure comment lines
3. **Paired Design**: Separate by LLM, each strategy is paired with baseline on the same File
4. **Statistical Tests**:
   - Continuous metrics (CHRF_Score, errors_per_LOC): Wilcoxon signed-rank test (two-tailed)
   - Binary metrics (Parsed, test_pass): McNemar exact test (two-tailed)

## Dependencies

- pandas
- numpy
- scipy
- statsmodels

