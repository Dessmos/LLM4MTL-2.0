"""Extraction reads what a response declared, never what it probably meant.

The extract stage is the first gate of the validation funnel, so a parser that
recovers a file name from surrounding prose, silently keeps the first of two
blocks claiming one file, or files an unrecognized artifact under `models/` is
answering RQ1 on the model's behalf.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm4mtl.domain import EXTRACTION_FAILED
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.semantic_tests.extraction.cli import extract_one
from llm4mtl.semantic_tests.extraction.models import ExtractionError, ResponseTarget
from llm4mtl.semantic_tests.extraction.parser import extract_files
from llm4mtl.semantic_tests.suites.discovery import suite_from_path
from llm4mtl.semantic_tests.validation import (
    ARTIFACT_INVALID,
    ValidationContext,
    observe_suite,
    reference_counts,
    technical_counts,
)

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
                self.assertEqual(
                    ["semantic_cases.json"], sorted(extract_files(block(info)))
                )

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
                with self.assertRaisesRegex(
                    ExtractionError, "role the contract does not define"
                ):
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


class ExtractionFailureStaysInTheFunnelTests(unittest.TestCase):
    """A response that fails extraction must stay countable.

    RQ1's invalid-test rate is computed over the generated tests the experiment
    asked for. If a malformed response produced no candidate at all, it would
    leave every stage after `extract`, and the weakest models would shrink the
    denominator instead of scoring badly in it.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.generated_tests_root = root / "generated"
        self.response = root / "Tree2Graph.md"
        self.response.write_text(
            "Here is the file: semantic_cases.json\n\n" + block("json"),
            encoding="utf-8",
        )
        self.target = ResponseTarget(
            response_path=self.response,
            llm="qwen2-5-coder-7b",
            strategy="only_prompt",
            task="Tree2Graph",
        )
        self.args = argparse.Namespace(
            generated_tests_root=self.generated_tests_root,
            suite_id=None,
            overwrite=False,
            dry_run=False,
        )
        self.adapter = EtlAdapter()

    def extract(self) -> tuple[bool, str]:
        return extract_one(self.target, self.args, self.adapter)

    def candidates(self) -> list[Path]:
        return sorted(self.generated_tests_root.glob("*/candidates/*/*/suite_*"))

    def test_selected_one_yields_one_persisted_invalid_candidate(self) -> None:
        ok, message = self.extract()

        self.assertFalse(ok)
        self.assertIn(EXTRACTION_FAILED, message)

        candidates = self.candidates()
        self.assertEqual(1, len(candidates))
        metadata = json.loads(
            (candidates[0] / "metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual("invalid", metadata["status"])
        self.assertFalse(metadata["artifact_validation"]["valid"])
        self.assertEqual(
            EXTRACTION_FAILED, metadata["artifact_validation"]["reason_code"]
        )

    def test_the_candidate_keeps_the_identity_of_the_response_it_came_from(
        self,
    ) -> None:
        self.extract()
        metadata = json.loads(
            (self.candidates()[0] / "metadata.json").read_text(encoding="utf-8")
        )

        self.assertEqual("etl", metadata["language"])
        self.assertEqual("Tree2Graph", metadata["task"])
        self.assertEqual("qwen2-5-coder-7b", metadata["llm"])
        self.assertEqual("only_prompt", metadata["strategy"])
        self.assertTrue(metadata["raw_output_file"].endswith("Tree2Graph.md"))

    def test_no_executable_artifact_is_fabricated(self) -> None:
        self.extract()
        suite = self.candidates()[0]

        self.assertEqual(["metadata.json"], sorted(p.name for p in suite.iterdir()))
        self.assertEqual([], metadata_free_files(suite))

    def test_it_is_never_sent_to_execution_and_counts_as_invalid(self) -> None:
        self.extract()
        suite = suite_from_path(
            self.candidates()[0], self.generated_tests_root.resolve(), "etl"
        )
        context = ValidationContext(adapter=self.adapter, workspace=None, timeout=1)

        def must_not_run(
            *_args, **_kwargs
        ):  # pragma: no cover - the point is it is unused
            raise AssertionError("an unreadable response must never reach Maven")

        with patch.object(self.adapter, "execute_suite", side_effect=must_not_run):
            verdict = observe_suite(suite, context)

        self.assertEqual(ARTIFACT_INVALID, verdict.status)
        self.assertIn(EXTRACTION_FAILED, verdict.error_summary)

        # One candidate selected, counted as invalid, none technically
        # executable and none reference-validated.
        technical = technical_counts([verdict], 1)
        reference = reference_counts([verdict], 1)
        self.assertEqual(
            {"selected": 1, "invalid": 1, "passed": 0},
            {k: technical[k] for k in ("selected", "invalid", "passed")},
        )
        self.assertEqual(
            {"selected": 1, "validated": 0, "invalid": 0},
            {k: reference[k] for k in ("selected", "validated", "invalid")},
        )


def metadata_free_files(suite: Path) -> list[str]:
    return sorted(
        str(item.relative_to(suite))
        for item in suite.rglob("*")
        if item.is_file() and item.name != "metadata.json"
    )


if __name__ == "__main__":
    unittest.main()
