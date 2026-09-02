"""Tests for generated-response discovery and explicit selection."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile
import unittest

from llm4mtl.semantic_tests.extraction.discovery import discover_responses


def _args(root: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "response": None,
        "suite_id": None,
        "responses_root": root,
        "llm": None,
        "strategy": None,
        "task": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ResponseDiscoveryTests(unittest.TestCase):

    def test_discovered_responses_are_sorted_and_hidden_files_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "gpt-5" / "grammar" / "First.md"
            second = root / "gpt-5" / "grammar" / "Second.md"
            first.parent.mkdir(parents=True)
            second.write_text("second", encoding="utf-8")
            first.write_text("first", encoding="utf-8")
            (first.parent / ".hidden.md").write_text("hidden", encoding="utf-8")

            targets = discover_responses(_args(root))

        self.assertEqual(
            [first.resolve(), second.resolve()],
            [item.response_path for item in targets],
        )
        self.assertEqual(["First", "Second"], [item.task for item in targets])
        self.assertTrue(all(item.llm == "gpt-5" for item in targets))
        self.assertTrue(all(item.strategy == "grammar" for item in targets))

    def test_explicit_responses_preserve_order_and_identity_overrides(self) -> None:
        root = Path("responses")
        paths = [Path("second.md"), Path("first.md")]

        targets = discover_responses(
            _args(
                root,
                response=paths,
                llm="model",
                strategy="strategy",
            )
        )

        self.assertEqual(
            [path.resolve() for path in paths],
            [item.response_path for item in targets],
        )
        self.assertEqual(["second", "first"], [item.task for item in targets])

    def test_suite_id_still_requires_one_explicit_response(self) -> None:
        with self.assertRaisesRegex(SystemExit, "single --response"):
            discover_responses(
                _args(
                    Path("responses"),
                    response=[Path("one.md"), Path("two.md")],
                    suite_id="suite_001",
                    llm="model",
                    strategy="strategy",
                )
            )


if __name__ == "__main__":
    unittest.main()
