"""Behavior locks for explicitly maintained legacy evaluation scripts."""

from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
from io import StringIO
from pathlib import Path
import subprocess
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from llm4mtl.paths import REPO_ROOT


def _load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load legacy script: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ETL_PARSER = _load_script(
    "legacy_etl_parser",
    REPO_ROOT / "pipeline/src/llm4mtl/evaluation/etl/ETL Parser/run_parser.py",
)
ETL_TESTS = _load_script(
    "legacy_etl_tests",
    REPO_ROOT / "pipeline/src/llm4mtl/evaluation/etl/ETL Test/run_all_tests.py",
)
QVTO_TESTS = _load_script(
    "legacy_qvto_tests",
    REPO_ROOT / "pipeline/src/llm4mtl/evaluation/qvto/QVT-O Test/run_all_tests.py",
)


class LegacyEtlParserSummaryTests(unittest.TestCase):

    def test_summary_preserves_grouping_sorting_and_totals(self) -> None:
        rows = [
            {
                "LLM": "zeta",
                "Strategy": "plain",
                "Parsed": False,
                "ProblemCount": 2,
            },
            {
                "LLM": "alpha",
                "Strategy": "grammar",
                "Parsed": True,
                "ProblemCount": 0,
            },
        ]
        output = StringIO()

        with redirect_stdout(output):
            ETL_PARSER.print_etl_parsed_rate_summary(rows)

        report = output.getvalue()
        self.assertLess(report.index("alpha"), report.index("zeta"))
        self.assertIn("100.0% (1/1)", report)
        self.assertIn("0.0% (0/1)", report)
        self.assertIn("OVERALL", report)
        self.assertIn("50.0% (1/2)", report)


class LegacyMavenTestRunnerTests(unittest.TestCase):

    def test_failure_detail_preserves_marker_precedence(self) -> None:
        cases = (
            (ETL_TESTS, "ETL parse errors: invalid token"),
            (QVTO_TESTS, "AssertionError: wrong model"),
        )
        for module, marker in cases:
            with self.subTest(module=module.__name__):
                output = f"Tests run: 1, Failures: 1\n{marker}\n"
                self.assertEqual(marker, module._error_detail(output))

    def test_run_test_preserves_success_failure_and_timeout_results(self) -> None:
        for module in (ETL_TESTS, QVTO_TESTS):
            with self.subTest(module=module.__name__, outcome="success"):
                completed = SimpleNamespace(returncode=0, stdout="", stderr="")
                with patch.object(module.subprocess, "run", return_value=completed):
                    self.assertEqual((True, ""), module.run_test("example.Test"))

            with self.subTest(module=module.__name__, outcome="failure"):
                completed = SimpleNamespace(
                    returncode=1,
                    stdout="Tests run: 1, Failures: 1\n",
                    stderr="",
                )
                with patch.object(module.subprocess, "run", return_value=completed):
                    self.assertEqual(
                        (False, "Tests run: 1, Failures: 1"),
                        module.run_test("example.Test"),
                    )

            with self.subTest(module=module.__name__, outcome="timeout"):
                timeout = subprocess.TimeoutExpired("mvn", 120)
                with patch.object(module.subprocess, "run", side_effect=timeout):
                    self.assertEqual(
                        (False, "TIMEOUT"),
                        module.run_test("example.Test"),
                    )


if __name__ == "__main__":
    unittest.main()
