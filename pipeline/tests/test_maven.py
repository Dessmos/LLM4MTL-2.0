"""Tests for Maven subprocess result summarization."""

from __future__ import annotations

import unittest

from llm4mtl.external_tools.maven import summarize_error


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


if __name__ == "__main__":
    unittest.main()
