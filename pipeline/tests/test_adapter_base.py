"""Tests for shared experiment-runner adapter utilities."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from llm4mtl.experiment_runner.adapters.base import hash_paths


class HashPathsTests(unittest.TestCase):

    def test_hash_is_independent_of_selection_order_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "first.txt"
            second = root / "second.txt"
            first.write_text("first", encoding="utf-8")
            second.write_text("second", encoding="utf-8")

            expected = hash_paths([first, second])

            self.assertEqual(expected, hash_paths([second, first, first]))

    def test_hash_includes_nested_file_names_and_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            nested = root / "nested"
            nested.mkdir()
            artifact = nested / "artifact.txt"
            artifact.write_text("before", encoding="utf-8")
            before = hash_paths([root])

            artifact.write_text("after", encoding="utf-8")

            self.assertNotEqual(before, hash_paths([root]))


if __name__ == "__main__":
    unittest.main()
