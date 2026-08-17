"""Behavior locks for the frozen per-language significance functions."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import tempfile
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from llm4mtl.evaluation.atl.scripts import file_utils as atl_file_utils
from llm4mtl.evaluation.atl.scripts import data_processing as atl_data_processing
from llm4mtl.evaluation.atl.scripts import significance_test as atl_significance
from llm4mtl.evaluation.atl.scripts import statistics as atl_statistics
from llm4mtl.evaluation.etl.scripts import file_utils as etl_file_utils
from llm4mtl.evaluation.etl.scripts import data_processing as etl_data_processing
from llm4mtl.evaluation.etl.scripts import significance_test as etl_significance
from llm4mtl.evaluation.etl.scripts import statistics as etl_statistics
from llm4mtl.evaluation.qvto.scripts import kruskal_wallis_by_mtl
from llm4mtl.evaluation.qvto.scripts import data_processing as qvto_data_processing
from llm4mtl.evaluation.qvto.scripts import significance_test as qvto_significance
from llm4mtl.evaluation.qvto.scripts import statistics as qvto_statistics


STATISTICS_MODULES: tuple[ModuleType, ...] = (
    atl_statistics,
    etl_statistics,
    qvto_statistics,
)

SIGNIFICANCE_MODULES: tuple[ModuleType, ...] = (
    atl_significance,
    etl_significance,
    qvto_significance,
)

DATA_PROCESSING_MODULES: tuple[ModuleType, ...] = (
    atl_data_processing,
    etl_data_processing,
    qvto_data_processing,
)


class LegacyMcnemarTests(unittest.TestCase):
    def test_contingency_table_and_exact_test_options_are_preserved(self) -> None:
        baseline = [True, True, False, False, np.nan]
        strategy = [True, False, True, False, True]

        for module in STATISTICS_MODULES:
            with self.subTest(module=module.__name__):
                with patch.object(
                    module,
                    "mcnemar",
                    return_value=SimpleNamespace(pvalue=0.25),
                ) as mcnemar_mock:
                    result = module.perform_mcnemar_test(baseline, strategy)

                self.assertEqual((0.25, 5, None), result)
                mcnemar_mock.assert_called_once_with(
                    [[1, 1], [2, 1]],
                    exact=True,
                    correction=False,
                )

    def test_no_discordant_pairs_skip_the_statistical_call(self) -> None:
        for module in STATISTICS_MODULES:
            with self.subTest(module=module.__name__):
                with patch.object(module, "mcnemar") as mcnemar_mock:
                    result = module.perform_mcnemar_test(
                        [True, False, np.nan],
                        [True, False, np.nan],
                    )

                self.assertEqual((1.0, 3, "No changes (b+c=0)"), result)
                mcnemar_mock.assert_not_called()

    def test_statistical_failure_is_returned_as_nan_with_the_original_reason(self) -> None:
        for module in STATISTICS_MODULES:
            with self.subTest(module=module.__name__):
                with patch.object(
                    module,
                    "mcnemar",
                    side_effect=RuntimeError("boom"),
                ):
                    p_value, pairs, reason = module.perform_mcnemar_test(
                        [True],
                        [False],
                    )

                self.assertTrue(np.isnan(p_value))
                self.assertEqual(1, pairs)
                self.assertEqual("Test failed: boom", reason)

    def test_mismatched_lengths_still_raise_assertion_error(self) -> None:
        for module in STATISTICS_MODULES:
            with self.subTest(module=module.__name__):
                with self.assertRaises(AssertionError):
                    module.perform_mcnemar_test([True], [])

    def test_pairing_counts_preserve_truth_and_nan_cells(self) -> None:
        baseline = [True, True, False, False, np.nan, np.nan]
        strategy = [True, False, True, False, True, np.nan]

        for module in SIGNIFICANCE_MODULES:
            with self.subTest(module=module.__name__):
                self.assertEqual(
                    (1, 1, 2, 2),
                    module._pairing_counts(baseline, strategy),
                )


class LegacyGroundTruthDiscoveryTests(unittest.TestCase):
    def test_preferred_directories_win_over_populated_fallbacks(self) -> None:
        cases = (
            (atl_file_utils, ".atl", "other_references"),
            (etl_file_utils, ".etl", "transformations"),
        )
        for module, suffix, preferred_name in cases:
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = module.Path(temp_dir)
                    preferred = root / "nested" / preferred_name
                    fallback = root / "fallback"
                    preferred.mkdir(parents=True)
                    fallback.mkdir()
                    (preferred / f"reference{suffix}").write_text(
                        "",
                        encoding="utf-8",
                    )
                    for index in range(5):
                        (fallback / f"candidate-{index}{suffix}").write_text(
                            "",
                            encoding="utf-8",
                        )

                    self.assertEqual(
                        str(preferred),
                        module.find_ground_truth_dir(root),
                    )

    def test_fallback_requires_at_least_five_files(self) -> None:
        for module, suffix in ((atl_file_utils, ".atl"), (etl_file_utils, ".etl")):
            with self.subTest(module=module.__name__):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = module.Path(temp_dir)
                    candidate = root / "candidate"
                    candidate.mkdir()
                    for index in range(4):
                        (candidate / f"reference-{index}{suffix}").write_text(
                            "",
                            encoding="utf-8",
                        )
                    self.assertIsNone(module.find_ground_truth_dir(root))

                    (candidate / f"reference-4{suffix}").write_text(
                        "",
                        encoding="utf-8",
                    )
                    self.assertEqual(
                        str(candidate),
                        module.find_ground_truth_dir(root),
                    )


class LegacySignificanceMarkerTests(unittest.TestCase):
    def test_metric_columns_keep_their_processing_order_and_formatting(self) -> None:
        summary = etl_data_processing.pd.DataFrame(
            [
                {
                    "LLM": "gpt-5",
                    "Strategy": "grammar",
                    "CHRF_Score": 0.5,
                    "errors_per_LOC": 0.25,
                    "Parsed_rate": 0.75,
                    "Parsed_test_pass": 0.125,
                    "unchanged": "value",
                }
            ]
        )
        results = etl_data_processing.pd.DataFrame(
            [
                {
                    "LLM": "gpt-5",
                    "strategy": "grammar",
                    "metric": metric,
                    "significant": True,
                }
                for metric in (
                    "CHRF_Score",
                    "Parsed",
                    "test_pass",
                )
            ]
        )

        for module in DATA_PROCESSING_MODULES:
            with self.subTest(module=module.__name__):
                marked = module.add_significance_markers(summary, results)

                self.assertEqual("0.500*", marked.loc[0, "CHRF_Score"])
                self.assertEqual("0.250", marked.loc[0, "errors_per_LOC"])
                self.assertEqual("0.750*", marked.loc[0, "Parsed_rate"])
                self.assertEqual("0.125**", marked.loc[0, "Parsed_test_pass"])
                self.assertEqual("value", marked.loc[0, "unchanged"])
                self.assertEqual(0.5, summary.loc[0, "CHRF_Score"])


class LegacyKruskalSummaryTests(unittest.TestCase):
    def test_report_preserves_model_order_and_nan_rendering(self) -> None:
        table = kruskal_wallis_by_mtl.pd.DataFrame(
            [
                {
                    "MTL": "Example",
                    "Metric": "ChrF",
                    "Claude": 0.25,
                    "Gemini": np.nan,
                    "GPT-5": 0.75,
                    "p-value": 0.125,
                    "sig": "",
                }
            ]
        )
        output = StringIO()

        with redirect_stdout(output):
            kruskal_wallis_by_mtl.print_report(table)

        report = output.getvalue()
        self.assertLess(report.index("Claude"), report.index("Gemini"))
        self.assertLess(report.index("Gemini"), report.index("GPT-5"))
        self.assertIn("ChrF", report)
        self.assertIn("0.2500", report)
        self.assertIn("N/A", report)
        self.assertIn("0.7500", report)
        self.assertIn("0.125", report)

    def test_summary_preserves_counts_reason_order_and_percentage(self) -> None:
        results = kruskal_wallis_by_mtl.pd.DataFrame(
            {
                "p_value": [0.01, np.nan, np.nan],
                "reason": ["", "all values identical", "all values identical"],
            }
        )
        output = StringIO()

        with redirect_stdout(output):
            kruskal_wallis_by_mtl._print_summary(results)

        self.assertIn("Total KW tests   : 3  (10 MTLs x 4 metrics)", output.getvalue())
        self.assertIn("Significant (*) : 1  (33%)", output.getvalue())
        self.assertIn("Non-calculable  : 2", output.getvalue())
        self.assertIn("   - all values identical  (2x)", output.getvalue())

    def test_csv_resolution_preserves_explicit_and_fallback_paths(self) -> None:
        explicit = kruskal_wallis_by_mtl._resolve_csv_path(
            "custom.csv",
            kruskal_wallis_by_mtl.Path("repository"),
        )
        fallback = kruskal_wallis_by_mtl._resolve_csv_path(
            None,
            kruskal_wallis_by_mtl.Path("repository"),
        )

        self.assertEqual(kruskal_wallis_by_mtl.Path("custom.csv"), explicit)
        self.assertEqual(
            kruskal_wallis_by_mtl.Path(
                "repository/QVT-O parser/benchmark_results_detailed.csv"
            ),
            fallback,
        )


if __name__ == "__main__":
    unittest.main()
