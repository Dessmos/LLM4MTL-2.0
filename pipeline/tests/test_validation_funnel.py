"""The funnel: artifact validity, technical executability, and oracle validity.

These are three separate gates observed from ONE execution against the reference
transformation. The test that matters most: a suite whose assertions fail is
technically executable and reference-invalid, so it stays in the executability
numerator and becomes a judged (failing) oracle rather than disappearing into a
"technical failure" bucket.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from llm4mtl.domain import GeneratedSuite
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.semantic_tests.reference_validation.runner import validate_suite
from llm4mtl.semantic_tests.suite_execution import (
    classify_maven_run,
    read_observation,
    record_observation,
)
from llm4mtl.semantic_tests.technical_validation.suite import check_suite, technical_row
from llm4mtl.semantic_tests.validation import ValidationContext, workspace_for

ASSERTION_FAILURE = CommandResult(
    exit_code=1,
    stdout="[ERROR] Tests run: 2, Failures: 1, Errors: 0\n[ERROR] expected: <4> but was: <3>",
    stderr="",
)
COMPILE_FAILURE = CommandResult(
    exit_code=1, stdout="[ERROR] COMPILATION ERROR :\n[ERROR] cannot find symbol", stderr=""
)
ALL_PASSED = CommandResult(
    exit_code=0, stdout="[INFO] Tests run: 2, Failures: 0, Errors: 0\n[INFO] BUILD SUCCESS", stderr=""
)

RENDERED_JAVA = """package org.eclipse.epsilon.examples.etl.generated;

public class GeneratedSmokeTest {
    @Test
    public void checksCount() throws Exception {
    }
}
"""


class FunnelFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self.suite_dir = (
            root / "generated_tests" / "SmokeTask" / "candidates" / "gpt-5" / "few_shot" / "suite_001"
        )
        (self.suite_dir / "models").mkdir(parents=True)
        (self.suite_dir / "GeneratedSmokeTest.java").write_text(RENDERED_JAVA, encoding="utf-8")
        (self.suite_dir / "models" / "in.model").write_text(
            '<?xml version="1.0"?><Root/>', encoding="utf-8"
        )
        self.write_metadata(valid=True)
        self.suite = GeneratedSuite(
            "etl",
            self.suite_dir,
            "SmokeTask",
            "gpt-5",
            "few_shot",
            "suite_001",
        )

        self.references_root = root / "references"
        self.references_root.mkdir()
        self.reference = self.references_root / "SmokeTask.etl"
        self.reference.write_text("rule R transform s : S!A to t : T!B { }\n", encoding="utf-8")

        self.harness = root / "harness"
        (self.harness / "src" / "test" / "java").mkdir(parents=True)
        self.observations_root = root / "observations"

    def write_metadata(self, *, valid: bool) -> None:
        validation = (
            {"valid": True}
            if valid
            else {
                "valid": False,
                "reason_code": "MISSING_SEMANTIC_CASES",
                "violations": ["no semantic_cases.json"],
            }
        )
        (self.suite_dir / "metadata.json").write_text(
            json.dumps(
                {"status": "candidate" if valid else "invalid", "artifact_validation": validation}
            ),
            encoding="utf-8",
        )

    def context(self) -> ValidationContext:
        return ValidationContext(
            adapter=EtlAdapter(references_root=self.references_root),
            workspace=workspace_for(self.harness, self.observations_root),
            timeout=60,
        )


class TechnicalValidationTests(FunnelFixture):
    def test_assertion_failure_is_technically_valid(self) -> None:
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=ASSERTION_FAILURE
        ):
            verdict = check_suite(self.suite, self.context())

        row = technical_row(verdict)
        self.assertTrue(verdict.is_technically_executable)
        self.assertEqual("TECHNICALLY_EXECUTABLE", verdict.status)
        self.assertEqual("False", row["assertions_passed"])
        self.assertEqual("assertion_failure", verdict.failure_stage)

    def test_compile_failure_is_not_technically_valid(self) -> None:
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=COMPILE_FAILURE
        ):
            verdict = check_suite(self.suite, self.context())

        self.assertFalse(verdict.is_technically_executable)
        self.assertEqual("NOT_EXECUTABLE", verdict.status)
        self.assertEqual("java_compilation", verdict.failure_stage)

    def test_an_artifact_invalid_suite_is_never_executed(self) -> None:
        self.write_metadata(valid=False)
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven",
            side_effect=AssertionError("Maven must not run for an artifact-invalid suite"),
        ):
            verdict = check_suite(self.suite, self.context())

        self.assertEqual("ARTIFACT_INVALID", verdict.status)
        self.assertFalse(verdict.is_technically_executable)

    def test_a_malformed_suite_is_rejected_before_maven(self) -> None:
        # Cheap static gates: a suite with no rendered harness, no models, or no
        # @Test methods cannot be executed, and must not reach the engine only
        # to fail there with an unrelated diagnostic.
        cases = {
            "no rendered harness": lambda: (self.suite_dir / "GeneratedSmokeTest.java").unlink(),
            "no models": lambda: (self.suite_dir / "models" / "in.model").unlink(),
            "no @Test methods": lambda: (self.suite_dir / "GeneratedSmokeTest.java").write_text(
                "public class GeneratedSmokeTest {}\n", encoding="utf-8"
            ),
            "unparsable model": lambda: (self.suite_dir / "models" / "in.model").write_text(
                "<broken", encoding="utf-8"
            ),
        }
        for label, break_it in cases.items():
            with self.subTest(case=label):
                self.setUp()
                break_it()
                with patch(
                    "llm4mtl.semantic_tests.suite_execution.run_maven",
                    side_effect=AssertionError("a malformed suite must not reach Maven"),
                ):
                    verdict = check_suite(self.suite, self.context())
                self.assertEqual("ARTIFACT_INVALID", verdict.status)

    def test_a_missing_reference_is_infrastructure_not_a_suite_defect(self) -> None:
        self.reference.unlink()
        verdict = check_suite(self.suite, self.context())

        self.assertEqual("INFRASTRUCTURE_ERROR", verdict.status)
        self.assertFalse(verdict.is_judged_as_oracle)


class ReferenceValidationTests(FunnelFixture):
    def test_a_failing_oracle_is_reference_invalid_not_a_technical_failure(self) -> None:
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=ASSERTION_FAILURE
        ):
            verdict = validate_suite(self.suite, self.context())

        self.assertEqual("REFERENCE_INVALID", verdict.status)
        self.assertTrue(verdict.is_technically_executable)
        self.assertTrue(verdict.is_judged_as_oracle)

    def test_a_passing_oracle_is_validated(self) -> None:
        with patch("llm4mtl.semantic_tests.suite_execution.run_maven", return_value=ALL_PASSED):
            verdict = validate_suite(self.suite, self.context())

        self.assertEqual("VALIDATED", verdict.status)
        self.assertTrue(verdict.is_judged_as_oracle)
        self.assertFalse(
            self.suite_dir.parents[3]
            .joinpath(
                "validated",
                self.suite.llm,
                self.suite.strategy,
                self.suite.suite_id,
            )
            .exists()
        )

    def test_an_unexecutable_suite_is_not_judged_as_an_oracle(self) -> None:
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=COMPILE_FAILURE
        ):
            verdict = validate_suite(self.suite, self.context())

        self.assertEqual("NOT_EXECUTABLE", verdict.status)
        self.assertFalse(verdict.is_judged_as_oracle)


class ObservationReuseTests(FunnelFixture):
    def test_the_technical_execution_is_not_repeated(self) -> None:
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=ASSERTION_FAILURE
        ) as maven:
            check_suite(self.suite, self.context())
            self.assertEqual(1, maven.call_count)

        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven",
            side_effect=AssertionError("the suite must not be executed twice"),
        ):
            verdict = validate_suite(self.suite, self.context())

        self.assertEqual("REFERENCE_INVALID", verdict.status)

    def test_an_observation_about_other_inputs_is_ignored(self) -> None:
        record_observation(
            self.observations_root, self.suite, self.reference, classify_maven_run(ALL_PASSED)
        )
        self.reference.write_text("rule Changed transform s : S!A to t : T!B { }\n", encoding="utf-8")

        self.assertIsNone(read_observation(self.observations_root, self.suite, self.reference))

        # A stale record must not decide the verdict: the suite is executed again.
        with patch(
            "llm4mtl.semantic_tests.suite_execution.run_maven", return_value=ASSERTION_FAILURE
        ) as maven:
            verdict = validate_suite(self.suite, self.context())

        self.assertEqual(1, maven.call_count)
        self.assertEqual("REFERENCE_INVALID", verdict.status)

    def test_concurrent_gates_share_one_physical_execution(self) -> None:
        context = self.context()
        observation = classify_maven_run(ALL_PASSED)
        with patch.object(
            context.adapter,
            "execute_suite",
            return_value=observation,
        ) as execute:
            with ThreadPoolExecutor(max_workers=8) as pool:
                verdicts = list(
                    pool.map(lambda _: check_suite(self.suite, context), range(8))
                )

        self.assertEqual(1, execute.call_count)
        self.assertTrue(all(verdict.is_technically_executable for verdict in verdicts))

    def test_persisted_inputs_are_typed_artifact_references(self) -> None:
        record_observation(
            self.observations_root,
            self.suite,
            self.reference,
            classify_maven_run(ALL_PASSED),
        )
        payload = json.loads(
            (
                self.observations_root
                / "SmokeTask"
                / "gpt-5"
                / "few_shot"
                / "suite_001"
                / "suite_execution.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual("generated_suite", payload["inputs"]["suite"]["role"])
        self.assertEqual("etl", payload["language"])
        self.assertEqual(
            "reference_transformation",
            payload["inputs"]["transformation"]["role"],
        )


if __name__ == "__main__":
    unittest.main()
