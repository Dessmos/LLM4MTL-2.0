"""Which harness phase failed, characterized against a real Surefire report.

The fixture is not synthetic: it is the report the ETL harness actually produced
for three deliberately broken tests — one failing assertion, one missing input
model, one wrong engine invocation. Maven's console for that same run printed
only ``Tests run: 3, Failures: 1, Errors: 2``, which is why a console-based
classifier reported all three as an assertion failure against a loaded model and
a started engine.

That mistake is scientific, not cosmetic: it counts a test that could not run as
technically executable, and its breakage as the generated oracle disagreeing
with the trusted reference.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.semantic_tests.suite_execution import classify_maven_run
from llm4mtl.semantic_tests.surefire import SurefireReport, read_surefire_reports

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "surefire"

# What Maven printed for the run the fixture came from.
CONSOLE = CommandResult(
    exit_code=1,
    stdout="[ERROR] Tests run: 3, Failures: 1, Errors: 2, Skipped: 0",
    stderr="",
)


def report_of(*, tests: int, failures: int, errors: int, messages: tuple[str, ...] = ()) -> SurefireReport:
    return SurefireReport(
        tests=tests, failures=failures, errors=errors, error_messages=messages
    )


class RealHarnessReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = read_surefire_reports(FIXTURES)
        self.assertIsNotNone(self.report, "the recorded harness report must be readable")

    def test_the_real_report_separates_failures_from_errors(self) -> None:
        self.assertEqual(3, self.report.tests)
        self.assertEqual(1, self.report.failures)
        self.assertEqual(2, self.report.errors)

    def test_a_missing_input_model_is_a_model_loading_failure(self) -> None:
        errors = [message for message in self.report.error_messages if "modelLoading" in message]
        self.assertTrue(errors, "the fixture must contain the model-loading error")
        self.assertIn("Resource not found", errors[0])

    def test_a_wrong_engine_invocation_surfaces_as_an_epsilon_error(self) -> None:
        errors = [message for message in self.report.error_messages if "engineRuntime" in message]
        self.assertTrue(errors, "the fixture must contain the engine-runtime error")
        self.assertIn("not found", errors[0])


class PhaseClassificationTests(unittest.TestCase):
    def test_a_model_loading_error_is_not_technically_executable(self) -> None:
        observation = classify_maven_run(
            CONSOLE,
            report_of(
                tests=1,
                failures=0,
                errors=1,
                messages=("modelLoadingFails: Resource not found: does-not-exist.model",),
            ),
        )

        self.assertFalse(observation.models_loaded)
        self.assertFalse(observation.engine_started)
        self.assertFalse(observation.is_technically_executable)
        self.assertFalse(observation.is_reference_valid)
        self.assertEqual("model_loading", observation.failure_stage)

    def test_an_engine_runtime_error_is_not_an_oracle_disagreement(self) -> None:
        observation = classify_maven_run(
            CONSOLE,
            report_of(
                tests=1,
                failures=0,
                errors=1,
                messages=("engineRuntimeFails: Type 'Tree!Tree' not found at org.eclipse.epsilon",),
            ),
        )

        self.assertTrue(observation.models_loaded)
        self.assertTrue(observation.engine_started)
        self.assertFalse(observation.is_technically_executable)
        self.assertEqual("engine_runtime", observation.failure_stage)

    def test_only_an_assertion_failure_is_an_oracle_disagreement(self) -> None:
        observation = classify_maven_run(CONSOLE, report_of(tests=1, failures=1, errors=0))

        self.assertTrue(observation.is_technically_executable)
        self.assertFalse(observation.assertions_passed)
        self.assertFalse(observation.is_reference_valid)
        self.assertEqual("assertion_failure", observation.failure_stage)

    def test_an_error_wins_over_a_coincident_assertion_failure(self) -> None:
        # The real report has both. A run that threw never reached a trustworthy
        # verdict, so it must not be recorded as one.
        observation = classify_maven_run(
            CONSOLE,
            report_of(
                tests=3,
                failures=1,
                errors=2,
                messages=("modelLoadingFails: Resource not found: does-not-exist.model",),
            ),
        )

        self.assertFalse(observation.is_technically_executable)
        self.assertEqual("model_loading", observation.failure_stage)

    def test_a_clean_run_passes(self) -> None:
        passing = CommandResult(exit_code=0, stdout="Tests run: 3, Failures: 0, Errors: 0", stderr="")
        observation = classify_maven_run(passing, report_of(tests=3, failures=0, errors=0))

        self.assertTrue(observation.is_technically_executable)
        self.assertTrue(observation.is_reference_valid)
        self.assertEqual("", observation.failure_stage)

    def test_no_report_falls_back_to_the_console(self) -> None:
        compile_failure = CommandResult(
            exit_code=1, stdout="[ERROR] COMPILATION ERROR :", stderr=""
        )
        observation = classify_maven_run(compile_failure, None)

        self.assertFalse(observation.compiled)
        self.assertEqual("java_compilation", observation.failure_stage)

    def test_no_report_never_turns_a_junit_error_into_an_oracle_failure(self) -> None:
        runtime_error = CommandResult(
            exit_code=1,
            stdout="[ERROR] Tests run: 1, Failures: 0, Errors: 1, Skipped: 0",
            stderr="[ERROR] java.lang.NullPointerException",
        )
        observation = classify_maven_run(runtime_error, None)

        self.assertFalse(observation.is_technically_executable)
        self.assertFalse(observation.assertions_evaluated)
        self.assertEqual("test_runtime", observation.failure_stage)

    def test_an_unknown_xml_error_is_not_attributed_to_the_engine(self) -> None:
        observation = classify_maven_run(
            CONSOLE,
            report_of(
                tests=1,
                failures=0,
                errors=1,
                messages=("generatedTest: java.lang.NullPointerException",),
            ),
        )

        self.assertEqual("test_runtime", observation.failure_stage)
        self.assertFalse(observation.is_technically_executable)


if __name__ == "__main__":
    unittest.main()
