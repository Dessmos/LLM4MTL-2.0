"""What extraction accepts as a generated suite.

The LLM authors semantic cases and models; the executable harness is rendered
deterministically in Python. A response that carries Java but no specification
must therefore never produce something a later stage would compile and run.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from llm4mtl.domain import INVALID_SEMANTIC_CASES
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.run_store.identity import InvalidRunIdError
from llm4mtl.semantic_tests.extraction.models import ResponseTarget
from llm4mtl.semantic_tests.extraction.semantic_cases import MISSING_SEMANTIC_CASES
from llm4mtl.semantic_tests.extraction.writer import write_suite
from llm4mtl.semantic_tests.suites.metadata import artifact_invalid_reason

HOSTILE_JAVA = """
package org.eclipse.epsilon.examples.etl.generated;

public class GeneratedTest {
    @Test
    public void runsArbitraryCode() throws Exception {
        Runtime.getRuntime().exec("touch /tmp/llm4mtl-should-never-run");
    }
}
"""

SEMANTIC_CASES = {
    "schemaVersion": 1,
    "testClass": "SmokeSemanticTest",
    "tests": [
        {
            "name": "producesTwoNodes",
            "models": [
                {
                    "name": "Src",
                    "kind": "emf",
                    "role": "source",
                    "path": "models/in.model",
                    "metamodelUri": "Src",
                },
                {"name": "Tgt", "kind": "emf", "role": "target", "metamodelUri": "Tgt"},
            ],
            "assertions": [
                {"kind": "count", "model": "Tgt", "type": "Node", "expected": 2}
            ],
        }
    ],
}

MODEL_XML = '<?xml version="1.0" encoding="UTF-8"?>\n<Src:Root xmlns:Src="Src"/>\n'


def response_markdown(*, with_spec: bool, with_java: bool) -> str:
    blocks = []
    if with_spec:
        blocks.append(
            "```json file=semantic_cases.json\n" + json.dumps(SEMANTIC_CASES, indent=2) + "\n```"
        )
    if with_java:
        blocks.append("```java file=GeneratedTest.java\n" + HOSTILE_JAVA + "\n```")
    blocks.append("```xml file=models/in.model\n" + MODEL_XML + "```")
    return "\n\n".join(blocks)


class ExtractionArtifactPolicyTests(unittest.TestCase):
    def write(
        self,
        root: Path,
        markdown: str,
        task: str = "SmokeTask",
        suite_id: str = "suite_001",
    ):
        response = root / "response.md"
        response.write_text(markdown, encoding="utf-8")
        target = ResponseTarget(response_path=response, llm="gpt-5", strategy="few_shot", task=task)
        args = argparse.Namespace(
            generated_tests_root=root / "generated_tests",
            suite_id=suite_id,
            overwrite=True,
            dry_run=False,
        )
        return write_suite(
            target,
            {**self._extract(markdown)},
            args,
            EtlAdapter(),
        )

    @staticmethod
    def _extract(markdown: str) -> dict[str, str]:
        from llm4mtl.semantic_tests.extraction.parser import extract_files

        return extract_files(markdown)

    def test_java_without_a_specification_is_discarded_and_the_suite_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir, validation = self.write(
                Path(temp_dir), response_markdown(with_spec=False, with_java=True)
            )

            self.assertFalse(validation.valid)
            self.assertEqual(MISSING_SEMANTIC_CASES, validation.reason_code)
            self.assertEqual([], sorted(suite_dir.glob("*.java")))
            self.assertNotEqual("", artifact_invalid_reason(suite_dir))

    def test_llm_java_is_replaced_by_the_rendered_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir, validation = self.write(
                Path(temp_dir), response_markdown(with_spec=True, with_java=True)
            )

            self.assertTrue(validation.valid)
            rendered = sorted(suite_dir.glob("*.java"))
            self.assertEqual(1, len(rendered))
            source = rendered[0].read_text(encoding="utf-8")
            self.assertNotIn("Runtime.getRuntime", source)
            self.assertIn("extends EtlTestBase", source)
            self.assertEqual("", artifact_invalid_reason(suite_dir))

    def test_metadata_records_why_a_suite_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir, _ = self.write(
                Path(temp_dir), response_markdown(with_spec=False, with_java=True)
            )
            metadata = json.loads((suite_dir / "metadata.json").read_text(encoding="utf-8"))

            self.assertEqual("invalid", metadata["status"])
            self.assertFalse(metadata["artifact_validation"]["valid"])
            self.assertEqual(
                MISSING_SEMANTIC_CASES, metadata["artifact_validation"]["reason_code"]
            )
            self.assertEqual("etl", metadata["language"])

    def test_malformed_semantic_cases_are_invalid_not_a_process_exit(self) -> None:
        malformed = (
            "```json file=semantic_cases.json\n"
            '{"schemaVersion": 1, "tests": []}\n'
            "```\n\n"
            "```xml file=models/in.model\n"
            f"{MODEL_XML}```"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir, validation = self.write(Path(temp_dir), malformed)

            self.assertFalse(validation.valid)
            self.assertEqual(INVALID_SEMANTIC_CASES, validation.reason_code)
            self.assertEqual([], list(suite_dir.glob("*.java")))

    def test_suite_id_cannot_escape_the_candidate_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaises(InvalidRunIdError):
                self.write(
                    root,
                    response_markdown(with_spec=True, with_java=False),
                    suite_id="../../outside",
                )
            self.assertFalse((root / "outside").exists())

    def test_an_existing_candidate_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            suite_dir, _ = self.write(
                root,
                response_markdown(with_spec=True, with_java=False),
            )
            original_metadata = (suite_dir / "metadata.json").read_bytes()

            with self.assertRaises(SystemExit) as raised:
                self.write(
                    root,
                    response_markdown(with_spec=False, with_java=True),
                )

            self.assertIn("immutable", str(raised.exception))
            self.assertEqual(original_metadata, (suite_dir / "metadata.json").read_bytes())
            self.assertEqual(1, len(list(suite_dir.glob("*.java"))))


class ArtifactValidityReaderTests(unittest.TestCase):
    def test_a_suite_without_a_recorded_verdict_is_refused(self) -> None:
        # Suites extracted before the policy may still contain LLM-authored Java,
        # so an absent verdict must not read as a passing one.
        with tempfile.TemporaryDirectory() as temp_dir:
            suite = Path(temp_dir)
            (suite / "metadata.json").write_text(
                json.dumps({"status": "candidate", "contract_enforcement": {"valid": True}}),
                encoding="utf-8",
            )
            self.assertIn("re-extract", artifact_invalid_reason(suite))

    def test_a_suite_with_no_metadata_at_all_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertNotEqual("", artifact_invalid_reason(Path(temp_dir)))


if __name__ == "__main__":
    unittest.main()
