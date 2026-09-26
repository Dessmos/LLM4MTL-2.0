"""How one Maven run of a generated suite is classified.

The observation this produces is the funnel's hinge, so each Maven outcome is
pinned here explicitly. The case that matters most for scientific validity: a
suite that compiles, discovers its tests, and runs the engine, but whose
assertions fail, is TECHNICALLY EXECUTABLE and REFERENCE-INVALID — never a
technical failure. Conflating the two removes wrong oracles from the
reference-pass population and understates the executability rate.
"""

from __future__ import annotations

import json
import unittest

from llm4mtl.domain.observations import FailureStage
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.suite_execution import classify_maven_run
from llm4mtl.semantic_tests.surefire import SurefireReport

COMPILE_FAILURE = """
[INFO] Compiling 1 source file
[ERROR] COMPILATION ERROR :
[ERROR] /src/test/java/GeneratedTest.java:[12,5] cannot find symbol
"""

NO_TESTS = """
[INFO] Tests are skipped.
[ERROR] No tests matching pattern GeneratedTest were executed!
"""

ASSERTION_FAILURE = """
[INFO] Running org.eclipse.epsilon.examples.etl.generated.GeneratedTest
[ERROR] Tests run: 3, Failures: 1, Errors: 0, Skipped: 0
[ERROR] countAssertion expected: <4> but was: <3>
"""

ENGINE_PARSE_FAILURE = """
[INFO] Running org.eclipse.epsilon.examples.etl.generated.GeneratedTest
[ERROR] Tests run: 1, Failures: 0, Errors: 1, Skipped: 0
[ERROR] java.lang.RuntimeException: ETL parse errors in Tree2Graph.etl
"""

ALL_PASSED = """
[INFO] Running org.eclipse.epsilon.examples.etl.generated.GeneratedTest
[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
"""


def maven(output: str, exit_code: int, timed_out: bool = False) -> CommandResult:
    return CommandResult(
        exit_code=exit_code, stdout=output, stderr="", timed_out=timed_out
    )


class ClassificationTests(unittest.TestCase):

    def test_assertion_failure_is_executable_but_not_reference_valid(self) -> None:
        observation = classify_maven_run(maven(ASSERTION_FAILURE, exit_code=1))

        self.assertTrue(observation.compiled)
        self.assertTrue(observation.tests_discovered)
        self.assertTrue(observation.engine_started)
        self.assertFalse(observation.assertions_passed)
        self.assertTrue(observation.is_technically_executable)
        self.assertFalse(observation.is_reference_valid)
        self.assertEqual("assertion_failure", observation.failure_stage)

    def test_all_assertions_passing_is_executable_and_reference_valid(self) -> None:
        observation = classify_maven_run(maven(ALL_PASSED, exit_code=0))

        self.assertTrue(observation.is_technically_executable)
        self.assertTrue(observation.is_reference_valid)
        self.assertTrue(observation.assertions_passed)
        self.assertEqual("", observation.failure_stage)

    def test_compile_failure_is_not_executable(self) -> None:
        observation = classify_maven_run(maven(COMPILE_FAILURE, exit_code=1))

        self.assertFalse(observation.compiled)
        self.assertFalse(observation.is_technically_executable)
        self.assertFalse(observation.is_reference_valid)
        self.assertEqual("java_compilation", observation.failure_stage)

    def test_undiscovered_tests_are_not_executable(self) -> None:
        observation = classify_maven_run(maven(NO_TESTS, exit_code=1))

        self.assertTrue(observation.compiled)
        self.assertFalse(observation.tests_discovered)
        self.assertFalse(observation.is_technically_executable)
        self.assertEqual("test_discovery", observation.failure_stage)

    def test_engine_parse_failure_is_infrastructure_not_a_wrong_oracle(self) -> None:
        # The transformation under test here is the trusted reference: if the
        # engine cannot parse it, the harness is broken, and the suite's oracle
        # has not been judged at all.
        observation = classify_maven_run(maven(ENGINE_PARSE_FAILURE, exit_code=1))

        self.assertFalse(observation.is_technically_executable)
        self.assertFalse(observation.is_reference_valid)
        self.assertTrue(observation.is_infrastructure_failure)
        self.assertEqual("transformation_parse", observation.failure_stage)

    def test_timeout_is_not_executable(self) -> None:
        observation = classify_maven_run(maven("", exit_code=124, timed_out=True))

        self.assertFalse(observation.is_technically_executable)
        self.assertTrue(observation.is_infrastructure_failure)
        self.assertEqual("timeout", observation.failure_stage)


    def test_a_timeout_keeps_the_compile_verdict(self) -> None:
        cases = ((COMPILE_FAILURE, False), (ALL_PASSED, True))
        for output, compiled in cases:
            with self.subTest(compiled=compiled):
                observation = classify_maven_run(
                    maven(output, exit_code=124, timed_out=True)
                )

                self.assertEqual("timeout", observation.failure_stage)
                self.assertTrue(observation.timed_out)
                self.assertEqual(compiled, observation.compiled)


class ConsoleFallbackTests(unittest.TestCase):
    """Runs that left no Surefire report are judged from the console alone."""

    def test_a_failed_build_without_failed_tests_is_unclassified(self) -> None:
        # Maven failed, yet the summary shows no failure and no error. The
        # console cannot say which phase broke, so no phase is claimed.
        observation = classify_maven_run(
            maven("[INFO] Tests run: 2, Failures: 0, Errors: 0", exit_code=1)
        )

        self.assertEqual("unclassified_runtime", observation.failure_stage)
        self.assertTrue(observation.tests_discovered)
        self.assertFalse(observation.assertions_evaluated)
        self.assertFalse(observation.is_technically_executable)

    def test_a_reactions_build_that_xtext_refused_is_a_parse_failure(self) -> None:
        # The Reactions harness validates the transformation while it builds.
        # The build stops before the test module, so no test ran and no report
        # exists: the engine refused the transformation, as ETL's parser does.
        output = (
            "[ERROR] ERROR:The type CreatedFatherReaction is already defined\n"
            "[INFO] BUILD FAILURE\n"
            "[ERROR] Failed to execute goal org.eclipse.xtext:xtext-maven-plugin:"
            "2.39.0:generate (default) on project consistency: Execution failed "
            "due to a severe validation error. -> [Help 1]\n"
        )

        observation = classify_maven_run(maven(output, exit_code=1))

        self.assertEqual("transformation_parse", observation.failure_stage)
        self.assertFalse(observation.assertions_passed)
        self.assertFalse(observation.is_technically_executable)

    def test_the_last_summary_line_decides(self) -> None:
        output = (
            "[INFO] Tests run: 1, Failures: 1, Errors: 0\n"
            "[INFO] Tests run: 4, Failures: 0, Errors: 0\n"
        )
        observation = classify_maven_run(maven(output, exit_code=0))

        self.assertTrue(observation.is_reference_valid)
        self.assertEqual("", observation.error_summary)


class ReportPhaseTests(unittest.TestCase):
    """Which harness phases a report-based failure says were reached."""

    def classify(self, report: SurefireReport):
        return classify_maven_run(maven("", exit_code=1), report)

    def test_each_phase_before_the_oracle_marks_the_phases_it_reached(self) -> None:
        cases = (
            ("Resource not found: in.model", "model_loading", False, False),
            ("ETL parse errors in T.etl", "transformation_parse", True, False),
            ("at org.eclipse.epsilon.Engine", "engine_runtime", True, True),
            ("java.lang.NullPointerException", "unclassified_runtime", False, False),
        )
        for message, stage, models_loaded, engine_started in cases:
            with self.subTest(stage=stage):
                observation = self.classify(
                    SurefireReport(
                        tests=1, failures=0, errors=1, error_messages=(message,)
                    )
                )

                self.assertEqual(stage, observation.failure_stage)
                self.assertTrue(observation.compiled)
                self.assertTrue(observation.tests_discovered)
                self.assertEqual(models_loaded, observation.models_loaded)
                self.assertEqual(engine_started, observation.engine_started)
                self.assertFalse(observation.assertions_evaluated)
                self.assertEqual(message, observation.error_summary)

    def test_a_harness_failure_summary_prefers_the_first_error(self) -> None:
        observation = self.classify(
            SurefireReport(
                tests=2,
                failures=1,
                errors=1,
                error_messages=("first: Resource not found",),
                failure_messages=("second: expected <1>",),
            )
        )

        self.assertEqual("first: Resource not found", observation.error_summary)

    def test_an_assertion_failure_summary_is_the_first_failure(self) -> None:
        observation = self.classify(
            SurefireReport(
                tests=2,
                failures=2,
                errors=0,
                failure_messages=("one: expected <1>", "two: expected <2>"),
            )
        )

        self.assertEqual("assertion_failure", observation.failure_stage)
        self.assertEqual("one: expected <1>", observation.error_summary)


class FailureStageVocabularyTests(unittest.TestCase):
    """The named failure stages are exactly the values the schema accepts."""

    # Values the schema accepts that no current code writes: no failure at all,
    # and the legacy catch-all kept only so old observations stay readable.
    NOT_NAMED = {"", "test_runtime"}

    def test_every_named_stage_is_a_schema_value_and_back(self) -> None:
        schema = json.loads(
            (TARGET.schemas / "suite-execution.schema.json").read_text(encoding="utf-8")
        )
        allowed = set(
            schema["properties"]["observation"]["properties"]["failure_stage"]["enum"]
        )
        named = {
            value
            for name, value in vars(FailureStage).items()
            if name.isupper() and isinstance(value, str)
        }

        for value in sorted(named):
            with self.subTest(named=value):
                self.assertIn(value, allowed)
        for value in sorted(allowed - self.NOT_NAMED):
            with self.subTest(schema=value):
                self.assertIn(value, named)


if __name__ == "__main__":
    unittest.main()
