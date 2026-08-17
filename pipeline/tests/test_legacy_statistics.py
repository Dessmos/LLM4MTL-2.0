"""Behavior locks for the frozen per-language significance functions."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from llm4mtl.evaluation.atl.scripts import statistics as atl_statistics
from llm4mtl.evaluation.etl.scripts import statistics as etl_statistics
from llm4mtl.evaluation.qvto.scripts import kruskal_wallis_by_mtl
from llm4mtl.evaluation.qvto.scripts import statistics as qvto_statistics


STATISTICS_MODULES: tuple[ModuleType, ...] = (
    atl_statistics,
    etl_statistics,
    qvto_statistics,
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


class LegacyKruskalSummaryTests(unittest.TestCase):
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
