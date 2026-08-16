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
        self.assertEqual("unclassified_runtime", observation.failure_stage)

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

        self.assertEqual("unclassified_runtime", observation.failure_stage)
        self.assertFalse(observation.is_technically_executable)


class NoTestRanTests(unittest.TestCase):
    """A suite that never executed a test must never look reference-valid.

    Both languages that pass ``-Dsurefire.failIfNoSpecifiedTests=false`` (QVT-O
    and Reactions) exit 0 when the test selector matches nothing. An exit code
    alone therefore says nothing about whether a test ran.
    """

    def test_a_report_counting_zero_tests_is_a_discovery_failure(self) -> None:
        observation = classify_maven_run(
            CommandResult(exit_code=0, stdout="", stderr=""),
            report_of(tests=0, failures=0, errors=0),
        )

        self.assertEqual("test_discovery", observation.failure_stage)
        self.assertFalse(observation.assertions_evaluated)
        self.assertFalse(observation.is_reference_valid)

    def test_exit_zero_without_any_test_summary_is_a_discovery_failure(self) -> None:
        observation = classify_maven_run(
            CommandResult(exit_code=0, stdout="[INFO] BUILD SUCCESS", stderr=""), None
        )

        self.assertEqual("test_discovery", observation.failure_stage)
        self.assertFalse(observation.is_reference_valid)

    def test_a_console_summary_of_zero_tests_is_a_discovery_failure(self) -> None:
        observation = classify_maven_run(
            CommandResult(
                exit_code=0,
                stdout="Tests run: 0, Failures: 0, Errors: 0, Skipped: 0",
                stderr="",
            ),
            None,
        )

        self.assertEqual("test_discovery", observation.failure_stage)
        self.assertFalse(observation.is_reference_valid)

    def test_a_console_run_that_did_execute_tests_still_passes(self) -> None:
        observation = classify_maven_run(
            CommandResult(
                exit_code=0,
                stdout="Tests run: 3, Failures: 0, Errors: 0, Skipped: 0",
                stderr="",
            ),
            None,
        )

        self.assertEqual("", observation.failure_stage)
        self.assertTrue(observation.is_reference_valid)


class PerEngineMarkerTests(unittest.TestCase):
    """Every message here was taken from a recorded run under artifacts/work/runs/."""

    def stage_for(self, message: str) -> str:
        return classify_maven_run(
            CONSOLE, report_of(tests=1, failures=0, errors=1, messages=(message,))
        ).failure_stage

    def test_emf_xmi_exceptions_are_model_loading(self) -> None:
        for message in (
            "aTest: org.eclipse.emf.ecore.xmi.PackageNotFoundException: "
            "Package with uri 'CPL' not found.",
            "aTest: org.eclipse.emf.ecore.xmi.ClassNotFoundException: "
            "Class 'EClassifier' is not found or is abstract.",
            "aTest: org.eclipse.emf.ecore.xmi.FeatureNotFoundException: "
            "Feature 'isLoaded' not found.",
        ):
            with self.subTest(message=message):
                self.assertEqual("model_loading", self.stage_for(message))

    def test_qvto_resource_creation_failure_is_model_loading(self) -> None:
        self.assertEqual(
            "model_loading",
            self.stage_for("aTest: Cannot create a resource for 'file:/tmp/out.xmi'"),
        )

    def test_atl_missing_model_is_model_loading(self) -> None:
        for message in (
            "aTest: Cannot find reference model amalthea",
            "aTest: Could not find model amalthea",
        ):
            with self.subTest(message=message):
                self.assertEqual("model_loading", self.stage_for(message))

    def test_vitruv_change_propagation_failures_are_engine_runtime(self) -> None:
        for message in (
            "aTest(Path): Cannot identify the packages of this change: "
            "TransactionalChangeImpl (empty)",
            "aTest(Path): dangling object "
            "tools.vitruv.methodologisttemplate.model.network.impl.SystemImpl@dffa30b detected",
        ):
            with self.subTest(message=message):
                self.assertEqual("engine_runtime", self.stage_for(message))

    def test_atl_vm_operation_lookup_failure_is_engine_runtime(self) -> None:
        self.assertEqual(
            "engine_runtime",
            self.stage_for(
                "aTest: Operation not found: AmaltheaToAscet_All : "
                "ASMModule.including(java.util.ArrayList)"
            ),
        )

    def test_genuinely_ambiguous_messages_stay_unclassified(self) -> None:
        for message in (
            # Could be the generated harness or the engine.
            "aTest(Path): class java.lang.String cannot be cast to class java.util.Collection",
            # Could be an unregistered model or a real type error.
            "aTest: Type 'Source!Tree' not found",
        ):
            with self.subTest(message=message):
                self.assertEqual("unclassified_runtime", self.stage_for(message))


if __name__ == "__main__":
    unittest.main()
