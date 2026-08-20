"""Source Diagnosis evidence is prepared after Stage 11, and only from it.

The ordering property is the one the proposal turns on: a generated test earns
the right to say something about a generated transformation by first passing on
the reference, and only its failure on the generated transformation is a
diagnosable semantic failure. These tests pin that the preparer builds nothing
before that point, attaches each report to exactly one semantic case, and states
honestly what it could not observe instead of inventing it.

The fixture is written inside the repository because every path a report cites
must stay contained; the run directory it creates is removed again.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.provenance import input_hashes
from llm4mtl.semantic_tests.diagnosis_preparation import (
    _index_counts,
    _match_assertion,
    diagnosis_artifact_references,
    diagnosis_response_dir,
    prepare_after_execution_stage,
    prepare_execution_diagnosis,
)
from llm4mtl.semantic_tests.failure_report import FailureReportError
from llm4mtl.semantic_tests.failure_report import (
    _failure_evidence,
    _surefire_test_case,
)
from llm4mtl.semantic_tests.execution_evidence import (
    STDOUT_FILENAME,
    SUREFIRE_DIRNAME,
)
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.transformation_execution.hashing import directory_sha256, file_sha256

LANGUAGE = "atl"
TASK = "AmaltheaToAscet_All"
CASE = "component_container_tasks_are_mapped_to_software_tasks"
METHOD = "componentContainerTasksAreMappedToSoftwareTasks"
ASSERTION_MESSAGE = "count assertion for OUT::AscetModule"

SEMANTIC_CASES: dict[str, Any] = {
    "schemaVersion": "1.0",
    "testClass": "GeneratedSemanticTest",
    "transformation": f"{TASK}.atl",
    "tests": [
        {
            "name": CASE,
            "scenarioKind": "batch_transformation",
            "models": [
                {
                    "name": "IN",
                    "kind": "emf",
                    "role": "source",
                    "path": "models/input.model",
                    "generated": True,
                    "metamodelUri": "http://vitruv.tools/methodologisttemplate/amalthea",
                },
                {
                    "name": "OUT",
                    "kind": "emf",
                    "role": "target",
                    "generated": False,
                    "metamodelUri": "http://vitruv.tools/methodologisttemplate/ascet",
                },
            ],
            "assertions": [
                {"kind": "count", "model": "OUT", "type": "AscetModule", "expected": 1},
                {"kind": "count", "model": "OUT", "type": "SoftwareTask", "expected": 2},
            ],
        }
    ],
}


class DiagnosisIndexCountTests(unittest.TestCase):
    def test_prepared_report_counts_preserve_status_scope_and_eligibility(self) -> None:
        pairs = [
            {
                "reports": [
                    {
                        "status": "created",
                        "scope": "execution_pair",
                        "eligible": True,
                    },
                    {"status": "refused", "eligible": False},
                ]
            },
            {"reports": []},
        ]

        self.assertEqual(
            {
                "failed_pairs": 2,
                "reports_created": 1,
                "reports_refused": 1,
                "pair_level_reports": 1,
                "diagnosis_eligible": 1,
                "pairs_without_reports": 1,
            },
            _index_counts(pairs),
        )


class SurefireTestCaseTests(unittest.TestCase):
    def test_failure_evidence_keeps_missing_field_errors_and_trace_rules(self) -> None:
        with self.assertRaises(KeyError):
            _failure_evidence({"kind": "runtime_error"}, ["trace"])

        summary, traces = _failure_evidence(None, ["trace"])
        self.assertTrue(all(value is None for value in summary.values()))
        self.assertEqual([], traces)

    def test_error_precedes_failure_and_preserves_exception_evidence(self) -> None:
        case = ET.fromstring(
            '<testcase classname="Example" name="fails" time="0.2">'
            '<failure type="AssertionError" message="failure">failure trace</failure>'
            '<error type="RuntimeException" message="runtime">runtime trace</error>'
            '</testcase>'
        )

        test_case, exception, trace = _surefire_test_case(
            REPO_ROOT / "report.xml",
            case,
        )

        self.assertEqual("error", test_case["status"])
        self.assertEqual("RuntimeException", test_case["failure_type"])
        self.assertEqual("runtime", test_case["message"])
        self.assertEqual(
            {"type": "RuntimeException", "message": "runtime"},
            exception,
        )
        self.assertEqual("runtime trace", trace)

    def test_passed_case_has_no_exception_or_trace(self) -> None:
        case = ET.fromstring(
            '<testcase classname="Example" name="passes" time="0.1" />'
        )

        test_case, exception, trace = _surefire_test_case(
            REPO_ROOT / "report.xml",
            case,
        )

        self.assertEqual("passed", test_case["status"])
        self.assertIsNone(test_case["message"])
        self.assertIsNone(exception)
        self.assertEqual("", trace)


EMPTY_SUREFIRE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<testsuite name="GeneratedSemanticTest" tests="0" failures="0" errors="0"/>\n'
)

# A harness that died before Surefire could run — and therefore report — any
# test method. The error belongs to the testsuite, not to a testcase.
SUITE_LEVEL_ERROR_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<testsuite name="GeneratedSemanticTest" tests="0" failures="0" errors="1">\n'
    '  <error message="ETL parse errors in Tree2Graph.etl" '
    'type="org.eclipse.epsilon.eol.exceptions.EolRuntimeException">'
    "at org.eclipse.epsilon.etl.EtlModule.parse(EtlModule.java:88)"
    "</error>\n"
    "  <system-err>[engine] refused the transformation</system-err>\n"
    "</testsuite>\n"
)


def _surefire_xml(message: str, element: str = "failure") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<testsuite name="GeneratedSemanticTest" tests="1" failures="1" errors="0">\n'
        f'  <testcase name="{METHOD}" classname="GeneratedSemanticTest" time="0.4">\n'
        f'    <{element} message="{message}" type="AssertionFailedError">'
        "stack trace line"
        f"</{element}>\n"
        "  </testcase>\n"
        "</testsuite>\n"
    )


class AssertionMatchingTests(unittest.TestCase):
    def test_explicit_assertion_id_is_selected_by_message_prefix(self) -> None:
        semantic_cases = {
            "tests": [
                {
                    "id": "case-1",
                    "assertions": [
                        {"id": "check-count", "message": "expected two nodes"},
                    ],
                }
            ]
        }

        self.assertEqual(
            "check-count",
            _match_assertion(
                semantic_cases,
                "case-1",
                "expected two nodes ==> expected: <2> but was: <1>",
            ),
        )

    def test_ambiguous_rendered_messages_are_refused(self) -> None:
        semantic_cases = {
            "tests": [
                {
                    "id": "case-1",
                    "assertions": [
                        {"id": "first", "message": "same message"},
                        {"id": "second", "message": "same message"},
                    ],
                }
            ]
        }

        with self.assertRaisesRegex(FailureReportError, "found 2"):
            _match_assertion(semantic_cases, "case-1", "same message: detail")


class DiagnosisPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = f"test-diagnosis-preparation-{uuid.uuid4().hex[:8]}"
        self.run_dir = TARGET.runs / self.run_id
        self.addCleanup(shutil.rmtree, self.run_dir, ignore_errors=True)
        self.fixture = self.run_dir / "fixture"
        (self.fixture / "suite" / "models").mkdir(parents=True)
        self.suite_dir = self.fixture / "suite"
        write_json(self.suite_dir / "semantic_cases.json", SEMANTIC_CASES)
        (self.suite_dir / "models" / "input.model").write_text(
            "<amalthea/>\n", encoding="utf-8"
        )
        (self.suite_dir / "GeneratedSemanticTest.java").write_text(
            "class GeneratedSemanticTest {}\n", encoding="utf-8"
        )
        self.transformation = self.fixture / f"{TASK}.atl"
        self.transformation.write_text("module Generated;\n", encoding="utf-8")
        self._write_manifest()

    # ------------------------------------------------------------------ fixture

    def _write_manifest(self) -> None:
        write_json(
            self.run_dir / "manifest.json",
            {
                "schema_version": "2.0",
                "run_id": self.run_id,
                "language": LANGUAGE,
                "task": TASK,
                "transformation_model": "gpt-5",
                "test_generation_model": "gpt-5",
                "transformation_strategy": "only_prompt",
                "test_generation_strategy": "few_shot",
                "seed": 1,
                "pipeline_variant": "full",
                "provenance": {
                    "renderer_version": "atl-junit-v1",
                    "input_hashes": input_hashes(LANGUAGE, TASK),
                },
            },
        )

    def _pair_root(self) -> Path:
        return (
            self.run_dir
            / "observations"
            / "generated_transformations"
            / file_sha256(self.transformation)
        )

    def _write_observation(
        self,
        *,
        root: Path,
        role: str,
        assertions_evaluated: bool = True,
        assertions_passed: bool = False,
        failure_stage: str = "assertion_failure",
    ) -> Path:
        path = (
            root
            / TASK
            / "gpt-5"
            / "few_shot"
            / "suite_001"
            / "suite_execution.json"
        )
        write_json(
            path,
            {
                "schema_version": "2.0",
                "language": LANGUAGE,
                "task": TASK,
                "llm": "gpt-5",
                "strategy": "few_shot",
                "suite_id": "suite_001",
                "inputs": {
                    "suite": {
                        "path": _relative(self.suite_dir),
                        "sha256": directory_sha256(self.suite_dir),
                        "role": "generated_suite",
                    },
                    "transformation": {
                        "path": _relative(self.transformation),
                        "sha256": file_sha256(self.transformation),
                        "role": role,
                    },
                },
                "observation": {
                    "compiled": True,
                    "tests_discovered": True,
                    "models_loaded": True,
                    "engine_started": True,
                    "assertions_evaluated": assertions_evaluated,
                    "assertions_passed": assertions_passed,
                    "timed_out": False,
                    "maven_exit_code": 0 if assertions_passed else 1,
                    "failure_stage": failure_stage,
                    "error_summary": "" if assertions_passed else "assertion failed",
                    "technically_executable": assertions_evaluated,
                    "reference_valid": assertions_evaluated and assertions_passed,
                },
            },
        )
        return path

    def _archive_evidence(self, observation: Path, xml: str) -> None:
        directory = observation.parent / "execution_evidence"
        (directory / SUREFIRE_DIRNAME).mkdir(parents=True, exist_ok=True)
        (directory / SUREFIRE_DIRNAME / "TEST-GeneratedSemanticTest.xml").write_text(
            xml, encoding="utf-8"
        )
        (directory / STDOUT_FILENAME).write_text("[INFO] BUILD FAILURE\n", encoding="utf-8")

    def _write_snapshot(self) -> Path:
        # Beside the suite observation, under the case that produced it.
        path = (
            self._pair_root()
            / TASK
            / "gpt-5"
            / "few_shot"
            / "suite_001"
            / "snapshots"
            / METHOD
            / "OUT.xmi"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<ascet/>\n", encoding="utf-8")
        return path

    def _write_stage_attempts(self, observation: Path, *, syntax_passed: bool = True) -> None:
        write_json(
            self.run_dir / "stages" / "syntax-validation" / "attempts" / "attempt-001" / "evidence.json",
            {
                "name": "transformation_parsing",
                "status": "completed",
                "counts": {"selected": 1, "passed": 1, "failed": 0},
                "details": {
                    "transformations": [str(self.transformation)],
                    "passed_transformations": (
                        [str(self.transformation)] if syntax_passed else []
                    ),
                    "failed_transformations": (
                        [] if syntax_passed else [str(self.transformation)]
                    ),
                    "diagnostics": {} if syntax_passed else {str(self.transformation): "parse error"},
                },
            },
        )
        write_json(
            self.run_dir / "stages" / "execution" / "attempts" / "attempt-001" / "result.json",
            {
                "schema_version": "2.0",
                "stage": "execution",
                "status": "failed",
                "outcome_code": "SEMANTIC_EXECUTION_FAILED",
                "counts": {
                    "selected_suites": 1,
                    "selected_transformations": 1,
                    "execution_pairs": 1,
                    "evaluated": 1,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "infrastructure_errors": 0,
                },
                "artifacts": {},
                "attempt": 1,
            },
        )
        write_json(
            self.run_dir / "stages" / "execution" / "attempts" / "attempt-001" / "evidence.json",
            {
                "name": "transformation_validation",
                "status": "completed",
                "counts": {
                    "selected_suites": 1,
                    "selected_transformations": 1,
                    "execution_pairs": 1,
                    "evaluated": 1,
                    "passed": 0,
                    "failed": 1,
                    "skipped": 0,
                    "infrastructure_errors": 0,
                },
                "details": {
                    "pairs": [
                        {
                            "suite": str(self.suite_dir),
                            "transformation": str(self.transformation),
                            "assertions_passed": False,
                            "failure_stage": "assertion_failure",
                            "outcome_status": None,
                            "evidence": str(observation),
                        }
                    ]
                },
            },
        )

    def _complete_failing_run(self, message: str | None = None) -> Path:
        observation = self._write_observation(root=self._pair_root(), role="generated_transformation")
        self._archive_evidence(
            observation,
            _surefire_xml(message or f"{ASSERTION_MESSAGE} ==&gt; expected: &lt;1&gt; but was: &lt;0&gt;"),
        )
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=True,
            failure_stage="",
        )
        self._write_stage_attempts(observation)
        return observation

    # -------------------------------------------------------------------- tests

    def test_failed_pair_yields_one_report_for_the_failing_case(self) -> None:
        self._complete_failing_run()
        self._write_snapshot()

        index = prepare_execution_diagnosis(self.run_dir, 1)

        self.assertEqual(1, index["counts"]["failed_pairs"])
        self.assertEqual(1, index["counts"]["reports_created"])
        self.assertEqual(1, index["counts"]["diagnosis_eligible"])
        entry = index["pairs"][0]["reports"][0]
        self.assertEqual(CASE, entry["test_case_id"])
        self.assertEqual("assertion-001", entry["assertion_id"])
        self.assertEqual("parser_passed_and_semantic_test_failed", entry["reason"])

        report = read_json(REPO_ROOT / entry["report"])
        result = report["test_case_result"]
        self.assertEqual(CASE, result["test_case"]["name"])
        # Only the failing case travels to diagnosis, never the whole suite.
        self.assertEqual("1", result["failure"]["expected"])
        self.assertEqual("0", result["failure"]["actual"])
        self.assertEqual("junit_assertion_message", result["failure"]["extraction"])
        self.assertEqual(1, len(result["actual_target_model"]))
        self.assertTrue(report["source_diagnosis"]["eligible"])
        self.assertEqual(
            "passed", result["reference_transformation_result"]["status"]
        )

    def test_the_bundle_satisfies_what_source_diagnosis_requires(self) -> None:
        """The two ends of the evidence contract are pinned to each other.

        Source Diagnosis validates the bundle in n8n, so the required field list
        lives in a workflow this suite cannot execute. Reading that list back and
        checking it against a real prepared bundle is what stops the two from
        drifting apart again, in either direction.
        """
        self._complete_failing_run()
        self._write_snapshot()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        report = read_json(REPO_ROOT / index["pairs"][0]["reports"][0]["report"])
        bundle = report["source_diagnosis"]["evidence_bundle"]

        for field in _required_evidence_fields("semantic_test_case_failure"):
            with self.subTest(field=field):
                self.assertIn(field, bundle)

        # The bundle carries more than a diagnosis reads. These extras are why
        # the workflow must check presence instead of an exact key set.
        for extra in ("changes", "syntax_status", "stack_traces", "maven_log_excerpt"):
            with self.subTest(extra=extra):
                self.assertIn(extra, bundle)
                self.assertNotIn(
                    extra, _required_evidence_fields("semantic_test_case_failure")
                )

        # An assertion failure carries no stack trace, so the required fields
        # must be tested for presence and never for truthiness.
        self.assertEqual([], bundle["stack_traces"])

        # The selector the failure is attached to survives into the bundle.
        failing = bundle["failing_test_case_or_assertion"]
        self.assertEqual(CASE, failing["test_case_id"])
        self.assertEqual("assertion-001", failing["assertion_id"])

    def test_a_real_assertion_mismatch_is_selected_for_diagnosis(self) -> None:
        """A recorded mismatch reaches Source Diagnosis on the evidence it has.

        The model-level comparator difference is still absent, so the report
        says ``available: false`` rather than inventing one. What the run did
        observe — the JUnit expected/actual pair, the target-model snapshot, the
        failing assertion — is real evidence, and selection is what decides
        whether it is offered at all. Requiring the comparator here would refuse
        every report the pipeline can currently produce.
        """
        self._complete_failing_run()
        self._write_snapshot()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])
        bundle = report["source_diagnosis"]["evidence_bundle"]

        # The observed mismatch, read verbatim out of the archived failure.
        self.assertEqual("1", report["test_case_result"]["failure"]["expected"])
        self.assertEqual("0", report["test_case_result"]["failure"]["actual"])
        # No comparator ran, and the report says exactly that.
        self.assertFalse(
            bundle["structured_actual_vs_expected_difference"]["available"]
        )

        references = diagnosis_artifact_references(self.run_dir, index)
        self.assertEqual(entry["report"], references["failure_report_path"])
        self.assertIn("failure_report_index", references)

    def test_a_diagnosable_attempt_gets_its_trace_directory(self) -> None:
        """The place a diagnosis records itself is prepared before it runs.

        The n8n write node cannot create the path it writes to, and the `mkdir`
        alternative needs a node a default n8n container does not ship. So the
        per-attempt directory is made here, where the attempt number is known,
        and the workflow only has to name files inside it.
        """
        self._complete_failing_run()
        self._write_snapshot()

        directory = diagnosis_response_dir(self.run_dir, 1)
        self.assertFalse(directory.exists())

        prepare_execution_diagnosis(self.run_dir, 1)

        self.assertTrue(directory.is_dir())
        self.assertEqual(
            ("responses", "source-diagnosis", "execution-attempt-001"),
            directory.relative_to(self.run_dir).parts,
        )

        # Re-reading a prepared attempt must leave it in place, so a run whose
        # evidence predates this can still be diagnosed.
        shutil.rmtree(directory)
        prepare_execution_diagnosis(self.run_dir, 1)
        self.assertTrue(directory.is_dir())

    def test_an_attempt_with_nothing_diagnosable_gets_no_trace_directory(self) -> None:
        """An empty directory would claim a diagnosis was possible when none was."""
        self._complete_failing_run()
        self._write_snapshot()
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=False,
            failure_stage="assertion_failure",
        )

        index = prepare_execution_diagnosis(self.run_dir, 1)

        self.assertEqual(0, index["counts"]["diagnosis_eligible"])
        self.assertFalse(diagnosis_response_dir(self.run_dir, 1).exists())

    def test_an_ineligible_report_is_never_selected_for_diagnosis(self) -> None:
        """Eligibility stays the gate that selection honours.

        A suite that never passed on the reference has not earned the right to
        say anything about a generated transformation, so its report exists as
        evidence but must not be offered for diagnosis.
        """
        self._complete_failing_run()
        self._write_snapshot()
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=False,
            failure_stage="assertion_failure",
        )

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        self.assertEqual("created", entry["status"])
        self.assertFalse(entry["eligible"])
        self.assertEqual("reference_result_not_passing", entry["reason"])

        references = diagnosis_artifact_references(self.run_dir, index)
        self.assertNotIn("failure_report_path", references)
        self.assertIn("failure_report_index", references)

    def test_unparseable_expected_and_actual_are_reported_as_unknown(self) -> None:
        self._complete_failing_run(message=f"{ASSERTION_MESSAGE} missing TaskA")
        self._write_snapshot()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])

        failure = report["test_case_result"]["failure"]
        self.assertIsNone(failure["expected"])
        self.assertIsNone(failure["actual"])
        self.assertEqual("unavailable", failure["extraction"])
        self.assertEqual(f"{ASSERTION_MESSAGE} missing TaskA", failure["message"])
        # The snapshot is still an observed actual result, so diagnosis stands.
        self.assertTrue(report["source_diagnosis"]["eligible"])

    def test_a_message_only_assertion_failure_is_still_diagnosable(self) -> None:
        # No snapshot, no comparator difference, and no parseable
        # expected/actual: what survives is the assertion's own recorded
        # message, and that is an observed fact about the failure.
        self._complete_failing_run(message=f"{ASSERTION_MESSAGE} missing TaskA")

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])
        evidence = report["test_case_result"]["observed_failure_evidence"]

        self.assertTrue(entry["eligible"])
        self.assertEqual(0, evidence["target_model_snapshots"])
        self.assertFalse(evidence["assertion_expected_actual"])
        self.assertTrue(evidence["recorded_exception"])

    def _throw_before_any_assertion(self) -> Path:
        """A test method that threw instead of reaching its first assertion.

        Surefire attributed the throw to one test method, so this is a per-case
        report - but no assertion was evaluated, which leaves the suite
        observation with ``assertions_evaluated`` false and the report's
        ``semantic_status`` at ``execution_error`` rather than ``failed``.
        """
        observation = self._write_observation(
            root=self._pair_root(),
            role="generated_transformation",
            assertions_evaluated=False,
            failure_stage="engine_runtime",
        )
        self._archive_evidence(
            observation,
            _surefire_xml("Type 'Source!Tree' not found", element="error"),
        )
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=True,
            failure_stage="",
        )
        self._write_stage_attempts(observation)
        return observation

    def test_a_runtime_error_is_diagnosed_without_an_assertion(self) -> None:
        self._throw_before_any_assertion()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])
        result = report["test_case_result"]

        # A validated test that throws on a generated transformation is a real
        # semantic failure of the pairing, and the proposal sends it to
        # diagnosis like any other.
        self.assertEqual("created", entry["status"])
        self.assertTrue(entry["eligible"])
        self.assertIsNone(entry["assertion_id"])
        self.assertEqual(CASE, entry["test_case_id"])
        self.assertEqual("runtime_error", result["failure"]["kind"])
        self.assertEqual("execution_error", result["semantic_status"])
        # Nothing is invented for a throw: there was no expected/actual.
        self.assertIsNone(result["failure"]["expected"])
        self.assertIsNone(result["failure"]["actual"])
        self.assertFalse(result["actual_vs_expected"]["available"])
        self.assertIsNone(result["assertion"])
        self.assertTrue(report["source_diagnosis"]["evidence_bundle"])

    def test_a_timeout_is_not_attributed_to_the_pairing(self) -> None:
        observation = self._write_observation(
            root=self._pair_root(),
            role="generated_transformation",
            assertions_evaluated=False,
            failure_stage="timeout",
        )
        self._archive_evidence(
            observation, _surefire_xml("interrupted", element="error")
        )
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=True,
            failure_stage="",
        )
        self._write_stage_attempts(observation)

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]

        self.assertFalse(entry["eligible"])
        self.assertEqual("failure_not_attributable_to_the_pairing", entry["reason"])

    def test_a_suite_that_did_not_pass_the_reference_is_not_diagnosable(self) -> None:
        observation = self._write_observation(
            root=self._pair_root(), role="generated_transformation"
        )
        self._archive_evidence(
            observation,
            _surefire_xml(f"{ASSERTION_MESSAGE} ==&gt; expected: &lt;1&gt; but was: &lt;0&gt;"),
        )
        self._write_stage_attempts(observation)

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]

        self.assertFalse(entry["eligible"])
        self.assertEqual("reference_result_not_passing", entry["reason"])

    def _failure_before_any_test_method(
        self, *, failure_stage: str = "engine_runtime", xml: str | None = None
    ) -> Path:
        observation = self._write_observation(
            root=self._pair_root(),
            role="generated_transformation",
            assertions_evaluated=False,
            failure_stage=failure_stage,
        )
        self._archive_evidence(observation, xml or SUITE_LEVEL_ERROR_XML)
        self._write_observation(
            root=self.run_dir / "observations",
            role="reference_transformation",
            assertions_passed=True,
            failure_stage="",
        )
        self._write_stage_attempts(observation)
        return observation

    def test_a_failure_before_any_test_method_yields_one_pair_level_report(self) -> None:
        self._failure_before_any_test_method()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        reports = index["pairs"][0]["reports"]

        self.assertEqual(1, len(reports))
        self.assertEqual(1, index["counts"]["pair_level_reports"])
        self.assertEqual(1, index["counts"]["reports_created"])
        self.assertEqual([], index["pairs"][0]["skipped"])
        self.assertEqual("execution_pair", reports[0]["scope"])
        self.assertTrue(reports[0]["eligible"])
        self.assertEqual(
            "parser_passed_and_execution_failed_before_any_test", reports[0]["reason"]
        )

        report = read_json(REPO_ROOT / reports[0]["report"])
        result = report["pair_result"]
        self.assertEqual("semantic_execution_pair_failure", report["report_type"])
        # The evidence the run did preserve is all there.
        self.assertEqual("engine_runtime", result["failure"]["failure_stage"])
        self.assertEqual(
            "org.eclipse.epsilon.eol.exceptions.EolRuntimeException",
            result["failure"]["failure_type"],
        )
        self.assertIn("ETL parse errors", result["failure"]["message"])
        self.assertTrue(result["execution"]["error"]["stack_traces"])
        self.assertTrue(result["execution"]["error"]["system_err"])
        self.assertTrue(result["execution"]["error"]["execution_log"]["path"])
        self.assertTrue(result["execution"]["error"]["surefire_reports"])
        self.assertEqual("passed", result["reference_transformation_result"]["status"])
        self.assertTrue(result["generated_transformation"]["content"])
        self.assertTrue(result["generated_test"]["content"])
        self.assertTrue(report["task_context"]["metamodel_constraints"])
        self.assertEqual(
            ["transformation_defect", "test_defect", "ambiguous"],
            report["source_diagnosis"]["allowed_classifications"],
        )

    def test_a_pair_level_report_invents_no_case_or_assertion(self) -> None:
        self._failure_before_any_test_method()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])
        result = report["pair_result"]
        bundle = report["source_diagnosis"]["evidence_bundle"]

        self.assertIsNone(entry["test_case_id"])
        self.assertIsNone(entry["assertion_id"])
        self.assertIsNone(result["test_case_id"])
        self.assertIsNone(result["assertion_id"])
        self.assertIsNone(result["failure"]["expected"])
        self.assertIsNone(result["failure"]["actual"])
        self.assertIsNone(bundle["failing_test_case_or_assertion"]["test_case_id"])
        self.assertIsNone(bundle["failing_test_case_or_assertion"]["assertion_id"])
        # The whole suite is supplied, unselected: which case failed is exactly
        # what the run did not record.
        self.assertEqual([CASE], bundle["generated_test"]["test_case_ids"])
        self.assertNotIn("test_case", result)
        self.assertNotIn("assertion", result)
        self.assertNotIn("test_case_result", report)

    def test_a_test_method_failure_uses_the_per_case_report(self) -> None:
        self._complete_failing_run()

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])

        self.assertEqual(0, index["counts"]["pair_level_reports"])
        self.assertEqual(1, index["counts"]["reports_created"])
        self.assertEqual("semantic_test_case_failure", report["report_type"])
        self.assertEqual(CASE, entry["test_case_id"])
        self.assertEqual("assertion-001", entry["assertion_id"])
        self.assertNotIn("pair_result", report)

    def _diagnose_report(self, entry: dict[str, object]) -> dict[str, object]:
        """Run the diagnosis subworkflow's own validation over a prepared report.

        Preparation and the subworkflow that consumes it are two halves of one
        contract, and only one of them is Python. Running the shipped node keeps
        a report type that Python marks eligible from being one the diagnosis
        silently cannot read.
        """
        report_path = REPO_ROOT / str(entry["report"])
        relative = report_path.relative_to(REPO_ROOT).as_posix()
        spec = {
            "workflow": str(
                REPO_ROOT / "workflows" / "n8n" / "subworkflows" / "diagnosis" / "llm-diagnosis.json"
            ),
            "node": "Validate Evidence Bundle",
            "input": [{"failure_report_text": report_path.read_text(encoding="utf-8")}],
            "nodes": {
                "Validate Input": {
                    "json": {
                        "run_id": self.run_id,
                        "execution_attempt": 1,
                        "provider": "openai",
                        "model": "gpt-5",
                        "evidence_ref": relative,
                    }
                }
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(spec, handle)
            spec_path = handle.name
        try:
            completed = subprocess.run(
                [
                    "node",
                    str(REPO_ROOT / "pipeline" / "tests" / "fixtures" / "run_master_code_node.js"),
                    spec_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        finally:
            Path(spec_path).unlink()
        return json.loads(completed.stdout)

    @unittest.skipUnless(shutil.which("node"), "the diagnosis subworkflow needs Node")
    def test_the_diagnosis_subworkflow_accepts_a_case_level_report(self) -> None:
        self._complete_failing_run()
        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]

        outcome = self._diagnose_report(entry)

        self.assertTrue(outcome["ok"], outcome.get("error"))
        self.assertEqual("test_case", outcome["result"]["scope"])
        self.assertEqual(entry["test_case_id"], outcome["result"]["test_case_id"])
        self.assertEqual(entry["assertion_id"], outcome["result"]["assertion_id"])

    @unittest.skipUnless(shutil.which("node"), "the diagnosis subworkflow needs Node")
    def test_the_diagnosis_subworkflow_accepts_a_pair_level_report(self) -> None:
        """A failure before any test method is diagnosable, not unreadable.

        Python marks these reports eligible, and the index selects them like any
        other, so a subworkflow that only understood ``semantic_test_case_failure``
        turned a real semantic failure into a workflow error.
        """
        self._failure_before_any_test_method()
        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        self.assertTrue(entry["eligible"])

        outcome = self._diagnose_report(entry)

        self.assertTrue(outcome["ok"], outcome.get("error"))
        self.assertEqual("execution_pair", outcome["result"]["scope"])
        # No case ran, so none is named - and none is invented either.
        self.assertIsNone(outcome["result"]["test_case_id"])
        self.assertIsNone(outcome["result"]["assertion_id"])
        bundle = outcome["result"]["evidence_bundle"]
        for field in _required_evidence_fields("semantic_execution_pair_failure"):
            with self.subTest(field=field):
                self.assertIn(field, bundle)
        # The whole suite stands in for the case that never ran, and the fields a
        # case-level bundle carries are absent rather than faked empty.
        self.assertIn("generated_test", bundle)
        for absent in ("input_model", "expected_output_or_properties", "actual_target_model"):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, bundle)

    @unittest.skipUnless(shutil.which("node"), "the diagnosis subworkflow needs Node")
    def test_the_diagnosis_subworkflow_accepts_a_case_level_throw(self) -> None:
        """A per-case report of a throw is diagnosable, not a workflow error.

        Python marks it eligible for the same reason it marks a lost assertion
        eligible, and the two differ in exactly two fields: the semantic status
        is ``execution_error`` because no assertion was evaluated, and the
        assertion is null because none was lost. A subworkflow that required
        ``failed`` and a named assertion turned every runtime failure of a
        generated transformation - the most common shape of a transformation
        defect - into a crashed run.
        """
        self._throw_before_any_assertion()
        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])

        self.assertEqual("semantic_test_case_failure", report["report_type"])
        self.assertEqual(
            "execution_error", report["test_case_result"]["semantic_status"]
        )
        self.assertEqual(CASE, entry["test_case_id"])
        self.assertIsNone(entry["assertion_id"])
        self.assertTrue(entry["eligible"])

        outcome = self._diagnose_report(entry)

        self.assertTrue(outcome["ok"], outcome.get("error"))
        self.assertEqual("test_case", outcome["result"]["scope"])
        self.assertEqual(CASE, outcome["result"]["test_case_id"])
        # Null travels on to the LLM request and back through the verdict
        # check, so nothing downstream has to invent an assertion either.
        self.assertIsNone(outcome["result"]["assertion_id"])
        bundle = outcome["result"]["evidence_bundle"]
        for field in _required_evidence_fields("semantic_test_case_failure"):
            with self.subTest(field=field):
                self.assertIn(field, bundle)
        self.assertTrue(bundle["stack_traces"])

    @unittest.skipUnless(shutil.which("node"), "the diagnosis subworkflow needs Node")
    def test_a_case_level_report_without_its_case_is_refused(self) -> None:
        """The case stays mandatory: only the assertion may be absent."""
        self._throw_before_any_assertion()
        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = dict(index["pairs"][0]["reports"][0])
        report_path = REPO_ROOT / str(entry["report"])
        report = read_json(report_path)
        report["test_case_result"]["test_case_id"] = None
        bundle = report["source_diagnosis"]["evidence_bundle"]
        bundle["failing_test_case_or_assertion"]["test_case_id"] = None
        write_json(report_path, report)

        outcome = self._diagnose_report(entry)

        self.assertFalse(outcome["ok"])
        self.assertIn("must name the failing test case", outcome["error"])

    @unittest.skipUnless(shutil.which("node"), "the diagnosis subworkflow needs Node")
    def test_an_unknown_report_type_is_still_refused(self) -> None:
        self._complete_failing_run()
        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = dict(index["pairs"][0]["reports"][0])
        report_path = REPO_ROOT / str(entry["report"])
        report = read_json(report_path)
        report["report_type"] = "semantic_something_else"
        write_json(report_path, report)

        outcome = self._diagnose_report(entry)

        self.assertFalse(outcome["ok"])
        self.assertIn("Unexpected failure report type", outcome["error"])

    def test_a_pair_level_timeout_is_not_eligible(self) -> None:
        self._failure_before_any_test_method(failure_stage="timeout")

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]
        report = read_json(REPO_ROOT / entry["report"])

        self.assertEqual("execution_pair", entry["scope"])
        self.assertFalse(entry["eligible"])
        self.assertEqual("failure_not_attributable_to_the_pairing", entry["reason"])
        self.assertIsNone(report["source_diagnosis"]["evidence_bundle"])

    def test_a_pair_level_infrastructure_failure_is_not_eligible(self) -> None:
        self._failure_before_any_test_method(failure_stage="infrastructure")

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]

        self.assertFalse(entry["eligible"])
        self.assertEqual("failure_not_attributable_to_the_pairing", entry["reason"])

    def test_preparation_leaves_the_recorded_execution_stage_untouched(self) -> None:
        self._failure_before_any_test_method()
        attempt_dir = (
            self.run_dir / "stages" / "execution" / "attempts" / "attempt-001"
        )
        before = {
            path.name: path.read_bytes() for path in sorted(attempt_dir.iterdir())
        }

        index = prepare_execution_diagnosis(self.run_dir, 1)

        after = {
            path.name: path.read_bytes() for path in sorted(attempt_dir.iterdir())
        }
        self.assertEqual(before, after)
        # The stage's own counts are the semantic result and stay exactly what
        # the execution observed; the index counts describe evidence only.
        counts = read_json(attempt_dir / "result.json")["counts"]
        self.assertEqual(
            {
                "selected_suites": 1,
                "selected_transformations": 1,
                "execution_pairs": 1,
                "evaluated": 1,
                "passed": 0,
                "failed": 1,
                "skipped": 0,
                "infrastructure_errors": 0,
            },
            counts,
        )
        self.assertNotIn("failed", index["counts"])
        self.assertNotIn("evaluated", index["counts"])

    def test_a_passing_pair_prepares_nothing(self) -> None:
        observation = self._write_observation(
            root=self._pair_root(),
            role="generated_transformation",
            assertions_passed=True,
            failure_stage="",
        )
        self._write_stage_attempts(observation)
        evidence = self.run_dir / "stages" / "execution" / "attempts" / "attempt-001" / "evidence.json"
        payload = read_json(evidence)
        payload["details"]["pairs"][0]["assertions_passed"] = True
        write_json(evidence, payload)

        index = prepare_execution_diagnosis(self.run_dir, 1)

        self.assertEqual([], index["pairs"])
        self.assertEqual(0, index["counts"]["reports_created"])

    def test_preparation_only_runs_for_a_failing_execution_stage(self) -> None:
        self._complete_failing_run()

        self.assertIsNone(
            prepare_after_execution_stage(
                self.run_dir, "reference-validation", {"counts": {"failed": 1}}, 1
            )
        )
        self.assertIsNone(
            prepare_after_execution_stage(
                self.run_dir, "execution", {"counts": {"failed": 0, "skipped": 1}}, 1
            )
        )
        self.assertFalse((self.run_dir / "diagnosis").exists())

        index = prepare_after_execution_stage(
            self.run_dir, "execution", {"counts": {"failed": 1}}, 1
        )
        self.assertIsNotNone(index)
        self.assertEqual(1, index["counts"]["reports_created"])

    def test_a_long_maven_log_is_cited_and_excerpted_not_inlined(self) -> None:
        observation = self._complete_failing_run()
        self._write_snapshot()
        log = observation.parent / "execution_evidence" / STDOUT_FILENAME
        log.write_text(
            "\n".join(f"[INFO] reactor line {index:05d}" for index in range(5000))
            + "\n[ERROR] BUILD FAILURE\n",
            encoding="utf-8",
        )

        index = prepare_execution_diagnosis(self.run_dir, 1)
        report = read_json(REPO_ROOT / index["pairs"][0]["reports"][0]["report"])
        cited = report["test_case_result"]["execution"]["error"]["execution_log"]

        self.assertEqual(5001, cited["lines"])
        self.assertTrue(cited["truncated"])
        self.assertLess(len(cited["excerpt"]), 9000)
        # The tail is what carries the failure, and the full stream stays one
        # hash away rather than being copied into every report.
        self.assertIn("[ERROR] BUILD FAILURE", cited["excerpt"])
        self.assertEqual(64, len(cited["sha256"]))

    def test_an_unassemblable_attempt_records_the_error_instead_of_vanishing(self) -> None:
        index = prepare_after_execution_stage(
            self.run_dir, "execution", {"counts": {"failed": 1}}, 7
        )

        self.assertIsNotNone(index)
        self.assertIn("no execution attempt 7", index["error"])
        self.assertEqual([], index["pairs"])

    def test_the_index_is_written_once_per_attempt(self) -> None:
        self._complete_failing_run()
        self._write_snapshot()

        first = prepare_execution_diagnosis(self.run_dir, 1)
        second = prepare_execution_diagnosis(self.run_dir, 1)

        self.assertEqual(first, second)

    def test_a_failed_parser_verdict_is_not_diagnosable(self) -> None:
        observation = self._write_observation(
            root=self._pair_root(), role="generated_transformation"
        )
        self._archive_evidence(
            observation,
            _surefire_xml(f"{ASSERTION_MESSAGE} ==&gt; expected: &lt;1&gt; but was: &lt;0&gt;"),
        )
        self._write_stage_attempts(observation, syntax_passed=False)

        index = prepare_execution_diagnosis(self.run_dir, 1)
        entry = index["pairs"][0]["reports"][0]

        self.assertFalse(entry["eligible"])
        self.assertEqual("transformation_parser_check_failed", entry["reason"])


def _required_evidence_fields(report_type: str) -> list[str]:
    """The evidence fields Source Diagnosis insists on for one report type.

    The two types carry different evidence: a case-level report has the input
    model, the expected output and the model-level difference, and a pair-level
    report has none of those because no case ran. Reading each list back from the
    workflow is what keeps preparation and the diagnosis from drifting apart.
    """
    workflow = json.loads(
        (
            REPO_ROOT
            / "workflows"
            / "n8n"
            / "subworkflows"
            / "diagnosis"
            / "llm-diagnosis.json"
        ).read_text(encoding="utf-8")
    )
    code = next(
        node["parameters"]["jsCode"]
        for node in workflow["nodes"]
        if node["name"] == "Validate Evidence Bundle"
    )
    declaration = re.search(
        re.escape(report_type) + r":\s*\{.*?required:\s*\[(.*?)\]", code, re.DOTALL
    )
    assert declaration is not None, f"the workflow declares no fields for {report_type}"
    return re.findall(r"'([a-z_]+)'", declaration.group(1))


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


if __name__ == "__main__":
    unittest.main()
