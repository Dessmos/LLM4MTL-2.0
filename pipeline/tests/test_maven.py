"""Tests for Maven subprocess execution and result summarization."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from llm4mtl.external_tools.maven import run_maven, summarize_error

# Writes to both streams, then outlives the one-second timeout below.
TALKATIVE_CHILD = (
    "import sys, time; "
    "sys.stdout.write('started'); sys.stdout.flush(); "
    "sys.stderr.write('partial error'); sys.stderr.flush(); "
    "time.sleep(30)"
)
SILENT_CHILD = "import time; time.sleep(30)"


class MavenErrorSummaryTests(unittest.TestCase):

    def test_first_three_interesting_lines_are_joined_in_output_order(self) -> None:
        output = (
            "noise\n"
            "  COMPILATION ERROR  \n"
            "error: missing symbol\n"
            "another Exception happened\n"
            "Errors: ignored after limit\n"
        )

        self.assertEqual(
            "COMPILATION ERROR | error: missing symbol | another Exception happened",
            summarize_error(output),
        )

    def test_fallback_is_the_last_line_and_empty_output_stays_empty(self) -> None:
        self.assertEqual("last line", summarize_error("first line\nlast line\n"))
        self.assertEqual("", summarize_error(" \n\t"))

    def test_summary_remains_bounded_to_five_hundred_characters(self) -> None:
        summary = summarize_error(f"error: {'x' * 600}")

        self.assertEqual(500, len(summary))


class RunMavenTimeoutTests(unittest.TestCase):

    def test_a_timed_out_command_becomes_a_timed_out_result(self) -> None:
        cases = (
            (TALKATIVE_CHILD, "started", "partial error\nTIMEOUT"),
            (SILENT_CHILD, "", "\nTIMEOUT"),
        )
        for script, stdout, stderr in cases:
            with self.subTest(stdout=stdout):
                with tempfile.TemporaryDirectory() as temp_dir:
                    result = run_maven(
                        [sys.executable, "-c", script], cwd=Path(temp_dir), timeout=1
                    )

                self.assertTrue(result.timed_out)
                self.assertEqual(124, result.exit_code)
                self.assertEqual(stdout, result.stdout)
                self.assertEqual(stderr, result.stderr)

    def test_a_finished_command_keeps_its_exit_code_and_text_output(self) -> None:
        script = "import sys; print('out'); sys.stderr.write('err'); sys.exit(3)"
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_maven(
                [sys.executable, "-c", script], cwd=Path(temp_dir), timeout=30
            )

        self.assertFalse(result.timed_out)
        self.assertEqual(3, result.exit_code)
        self.assertEqual("out\n", result.stdout)
        self.assertEqual("err", result.stderr)


if __name__ == "__main__":
    unittest.main()
