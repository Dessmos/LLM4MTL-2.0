"""How one Maven run of a generated suite is classified.

The observation this produces is the funnel's hinge, so each Maven outcome is
pinned here explicitly. The case that matters most for scientific validity: a
suite that compiles, discovers its tests, and runs the engine, but whose
assertions fail, is TECHNICALLY EXECUTABLE and REFERENCE-INVALID — never a
technical failure. Conflating the two removes wrong oracles from the
reference-pass population and understates the executability rate.
"""

from __future__ import annotations

import unittest

from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.semantic_tests.suite_execution import classify_maven_run

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
    return CommandResult(exit_code=exit_code, stdout=output, stderr="", timed_out=timed_out)


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


if __name__ == "__main__":
    unittest.main()
