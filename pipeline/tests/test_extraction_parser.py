"""Extraction reads what a response declared, never what it probably meant.

The extract stage is the first gate of the validation funnel, so a parser that
recovers a file name from surrounding prose, silently keeps the first of two
blocks claiming one file, or files an unrecognized artifact under `models/` is
answering RQ1 on the model's behalf.
"""

from __future__ import annotations

import argparse
import unittest
from pathlib import Path

from llm4mtl.semantic_tests.extraction.cli import extract_one
from llm4mtl.semantic_tests.extraction.models import ExtractionError, ResponseTarget
from llm4mtl.semantic_tests.extraction.parser import extract_files

CASES = '{"schemaVersion": 1, "tests": []}'


def block(info: str, content: str = CASES) -> str:
    return f"```{info}\n{content}\n```\n"


class DeclaredNamesOnlyTests(unittest.TestCase):
    def test_a_named_block_is_extracted(self) -> None:
        extracted = extract_files(block("json file=semantic_cases.json"))

        self.assertEqual({"semantic_cases.json": CASES + "\n"}, extracted)

    def test_every_declaration_spelling_the_contract_allows_still_works(self) -> None:
        for info in (
            "json file=semantic_cases.json",
            "json filename=semantic_cases.json",
            "json path=semantic_cases.json",
            'json file="semantic_cases.json"',
            "semantic_cases.json",
        ):
            with self.subTest(info=info):
                self.assertEqual(["semantic_cases.json"], sorted(extract_files(block(info))))

    def test_prose_before_a_block_is_not_used_as_its_name(self) -> None:
        markdown = (
            "Below is the specification, file: semantic_cases.json, as requested.\n\n"
            + block("json")
        )

        with self.assertRaisesRegex(ExtractionError, "does not name a file"):
            extract_files(markdown)

    def test_a_bare_language_tag_is_ambiguous(self) -> None:
        for info in ("json", "xml", "java", ""):
            with self.subTest(info=info):
                with self.assertRaisesRegex(ExtractionError, "does not name a file"):
                    extract_files(block(info))

    def test_a_response_with_no_fenced_block_is_empty_not_an_error(self) -> None:
        # The caller already reports "nothing to extract"; that is a different
        # fact from "this response declared something unreadable".
        self.assertEqual({}, extract_files("No code here at all.\n"))


class UniqueIdentityTests(unittest.TestCase):
    def test_two_blocks_claiming_one_artifact_are_refused(self) -> None:
        markdown = block("xml file=models/input.model", "<a/>") + block(
            "xml file=models/input.model", "<b/>"
        )

        with self.assertRaisesRegex(ExtractionError, "already declared"):
            extract_files(markdown)

    def test_a_collision_after_canonicalization_is_also_refused(self) -> None:
        # Both canonicalize to `semantic_cases.json`; keeping the first would
        # silently discard the second specification.
        markdown = block("json file=semantic_cases.json") + block(
            "json file=spec/semantic_cases.json"
        )

        with self.assertRaisesRegex(ExtractionError, "already declared"):
            extract_files(markdown)

    def test_distinct_artifacts_are_all_kept(self) -> None:
        markdown = (
            block("json file=semantic_cases.json")
            + block("xml file=models/a.model", "<a/>")
            + block("xml file=models/b.model", "<b/>")
        )

        self.assertEqual(
            ["models/a.model", "models/b.model", "semantic_cases.json"],
            sorted(extract_files(markdown)),
        )


class KnownArtifactRoleTests(unittest.TestCase):
    def test_a_file_the_contract_does_not_define_is_refused(self) -> None:
        for declared in ("pom.xml.bak", "build.gradle", "notes.md", "run.sh"):
            with self.subTest(declared=declared):
                with self.assertRaisesRegex(ExtractionError, "role the contract does not define"):
                    extract_files(block(f"text file={declared}", "x"))

    def test_a_model_file_outside_models_is_not_relocated(self) -> None:
        with self.assertRaisesRegex(ExtractionError, "outside models/"):
            extract_files(block("xml file=input.model", "<a/>"))

    def test_a_model_file_in_a_foreign_directory_is_not_relocated(self) -> None:
        with self.assertRaisesRegex(ExtractionError, "outside models/"):
            extract_files(block("xml file=src/test/resources/input.model", "<a/>"))

    def test_a_declared_path_escaping_the_suite_is_refused(self) -> None:
        for declared in ("../models/input.model", "/etc/models/input.model"):
            with self.subTest(declared=declared):
                with self.assertRaises(ExtractionError):
                    extract_files(block(f"xml file={declared}", "<a/>"))

    def test_model_paths_under_models_are_kept_verbatim(self) -> None:
        extracted = extract_files(block("xml file=models/nested/input.model", "<a/>"))

        self.assertEqual(["models/nested/input.model"], sorted(extracted))


class ExtractionFailureIsReportedNotRaisedTests(unittest.TestCase):
    def test_the_stage_records_a_failure_and_keeps_going(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            response = Path(temp_dir) / "Tree2Graph.md"
            response.write_text(
                "Here is the file: semantic_cases.json\n\n" + block("json"),
                encoding="utf-8",
            )
            target = ResponseTarget(
                response_path=response, llm="qwen", strategy="only_prompt", task="Tree2Graph"
            )
            args = argparse.Namespace(
                generated_tests_root=Path(temp_dir) / "generated",
                suite_id=None,
                overwrite=False,
                dry_run=False,
            )

            extracted, message = extract_one(target, args, adapter=None)

            self.assertFalse(extracted)
            self.assertIn("cannot extract artifacts", message)
            self.assertIn("does not name a file", message)
            # No candidate directory is invented for a response that declared
            # no readable specification.
            self.assertFalse((Path(temp_dir) / "generated").exists())


if __name__ == "__main__":
    unittest.main()
