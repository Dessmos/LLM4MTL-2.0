"""Raw execution evidence must outlive the workspace it was produced in.

Maven writes Surefire XML into the engine workspace's ``target/`` directory and
every execution begins with ``mvn clean``, so the reports explaining execution N
cease to exist the moment execution N+1 starts. Source Diagnosis runs after the
whole stage. These tests pin the property that makes that safe: the evidence is
archived into the run's permanent artifacts at the moment the observation is
recorded, complete and attributed, and archiving changes no verdict.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.domain import GeneratedSuite
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.semantic_tests.execution_evidence import (
    MANIFEST_FILENAME,
    STDERR_FILENAME,
    STDOUT_FILENAME,
    SUREFIRE_DIRNAME,
    archived_execution_evidence,
    capture_execution_evidence,
    evidence_dir,
)
from llm4mtl.semantic_tests.suite_execution import (
    GENERATED_TRANSFORMATION_ROLE,
    REFERENCE_TRANSFORMATION_ROLE,
    classify_maven_run,
    observation_path,
    read_observation,
    record_observation,
)
from llm4mtl.semantic_tests.surefire import read_surefire_reports

REPORT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="GeneratedTest" tests="2" failures="1" errors="0">
  <testcase name="mapsRoot"/>
  <testcase name="mapsChildren">
    <failure message="expected: &lt;2&gt; but was: &lt;1&gt;" type="AssertionFailedError"/>
  </testcase>
</testsuite>
"""

# Long enough that any 500-character summarisation would be visible.
LONG_STDOUT = "\n".join(f"[INFO] reactor line {index:04d}" for index in range(400))


def _suite(root: Path, suite_id: str = "suite_001") -> GeneratedSuite:
    path = root / "suites" / suite_id
    (path / "models").mkdir(parents=True, exist_ok=True)
    (path / "GeneratedTest.java").write_text("class GeneratedTest {}\n", encoding="utf-8")
    return GeneratedSuite(
        language="etl",
        path=path,
        task="SmokeTask",
        llm="gpt-5",
        strategy="few_shot",
        suite_id=suite_id,
    )


def _transformation(root: Path, name: str) -> Path:
    path = root / name
    path.write_text(f"rule {name}\n", encoding="utf-8")
    return path


class _Harness:
    """A stand-in workspace whose `mvn clean` really does delete the reports."""

    def __init__(self, root: Path) -> None:
        self.reports_dir = root / "workspace" / "target" / "surefire-reports"

    def run(self, *, stdout: str, stderr: str, exit_code: int, reports: dict[str, str]):
        # `mvn clean` first: whatever the previous execution left is gone.
        if self.reports_dir.exists():
            for stale in self.reports_dir.iterdir():
                stale.unlink()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        for name, content in reports.items():
            (self.reports_dir / name).write_text(content, encoding="utf-8")
        result = CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)
        report = read_surefire_reports(self.reports_dir)
        evidence = capture_execution_evidence(result, self.reports_dir, report)
        return classify_maven_run(result, report), evidence

    def clean(self) -> None:
        if self.reports_dir.exists():
            for stale in self.reports_dir.iterdir():
                stale.unlink()


class EvidenceSurvivesTheWorkspaceTests(unittest.TestCase):
    def test_pair_n_evidence_survives_pair_n_plus_1_running_maven_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            observations = root / "observations"
            harness = _Harness(root)

            first_suite = _suite(root, "suite_001")
            first_transformation = _transformation(root, "first.etl")
            observation, evidence = harness.run(
                stdout=LONG_STDOUT,
                stderr="[ERROR] first pair stderr",
                exit_code=1,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )
            first_path = record_observation(
                observations,
                first_suite,
                first_transformation,
                observation,
                transformation_role=GENERATED_TRANSFORMATION_ROLE,
                evidence=evidence,
            )

            # Pair 2 runs in the same workspace and wipes pair 1's reports.
            second_suite = _suite(root, "suite_002")
            second_transformation = _transformation(root, "second.etl")
            second_observation, second_evidence = harness.run(
                stdout="[INFO] second pair",
                stderr="",
                exit_code=0,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )
            record_observation(
                observations,
                second_suite,
                second_transformation,
                second_observation,
                transformation_role=GENERATED_TRANSFORMATION_ROLE,
                evidence=second_evidence,
            )
            harness.clean()

            self.assertFalse(list(harness.reports_dir.glob("TEST-*.xml")))

            archived = archived_execution_evidence(first_path)
            self.assertIsNotNone(archived.directory)
            self.assertEqual(1, len(archived.surefire_reports))
            self.assertEqual(REPORT_XML, archived.surefire_reports[0].read_text(encoding="utf-8"))
            self.assertEqual(
                "[ERROR] first pair stderr",
                (archived.directory / STDERR_FILENAME).read_text(encoding="utf-8"),
            )

    def test_maven_output_is_archived_untruncated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            observation, evidence = harness.run(
                stdout=LONG_STDOUT,
                stderr="[ERROR] " + "x" * 4000,
                exit_code=1,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )
            path = record_observation(
                root / "observations",
                _suite(root),
                _transformation(root, "only.etl"),
                observation,
                evidence=evidence,
            )
            directory = evidence_dir(path)

            self.assertEqual(
                LONG_STDOUT, (directory / STDOUT_FILENAME).read_text(encoding="utf-8")
            )
            self.assertEqual(
                4008, len((directory / STDERR_FILENAME).read_text(encoding="utf-8"))
            )
            # The short derived summary stays on the observation and does not
            # replace the raw stream.
            self.assertLessEqual(len(observation.error_summary), 500)
            self.assertGreater(len(LONG_STDOUT), 500)

    def test_all_surefire_reports_are_preserved_verbatim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            second = REPORT_XML.replace("GeneratedTest", "OtherTest")
            observation, evidence = harness.run(
                stdout="[INFO] two reports",
                stderr="",
                exit_code=1,
                reports={
                    "TEST-GeneratedTest.xml": REPORT_XML,
                    "TEST-OtherTest.xml": second,
                },
            )
            path = record_observation(
                root / "observations",
                _suite(root),
                _transformation(root, "only.etl"),
                observation,
                evidence=evidence,
            )
            surefire = evidence_dir(path) / SUREFIRE_DIRNAME

            self.assertEqual(
                ["TEST-GeneratedTest.xml", "TEST-OtherTest.xml"],
                sorted(item.name for item in surefire.iterdir()),
            )
            self.assertEqual(
                REPORT_XML, (surefire / "TEST-GeneratedTest.xml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                second, (surefire / "TEST-OtherTest.xml").read_text(encoding="utf-8")
            )


class EvidenceAttributionTests(unittest.TestCase):
    def manifest_for(self, role: str) -> dict:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            observation, evidence = harness.run(
                stdout="[INFO] run",
                stderr="",
                exit_code=1,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )
            path = record_observation(
                root / "observations",
                _suite(root),
                _transformation(root, "transformation.etl"),
                observation,
                transformation_role=role,
                evidence=evidence,
            )
            return json.loads(
                (evidence_dir(path) / MANIFEST_FILENAME).read_text(encoding="utf-8")
            )

    def test_evidence_names_the_reference_transformation_it_belongs_to(self) -> None:
        manifest = self.manifest_for(REFERENCE_TRANSFORMATION_ROLE)

        self.assertEqual(
            REFERENCE_TRANSFORMATION_ROLE, manifest["inputs"]["transformation"]["role"]
        )

    def test_evidence_names_the_generated_transformation_it_belongs_to(self) -> None:
        manifest = self.manifest_for(GENERATED_TRANSFORMATION_ROLE)

        self.assertEqual(
            GENERATED_TRANSFORMATION_ROLE, manifest["inputs"]["transformation"]["role"]
        )

    def test_evidence_carries_the_full_suite_and_input_identity(self) -> None:
        manifest = self.manifest_for(GENERATED_TRANSFORMATION_ROLE)

        for field, expected in (
            ("language", "etl"),
            ("task", "SmokeTask"),
            ("llm", "gpt-5"),
            ("strategy", "few_shot"),
            ("suite_id", "suite_001"),
        ):
            with self.subTest(field=field):
                self.assertEqual(expected, manifest[field])
        self.assertEqual(64, len(manifest["inputs"]["transformation"]["sha256"]))
        self.assertEqual(64, len(manifest["inputs"]["suite"]["sha256"]))
        validate_artifact("execution-evidence", manifest)

    def test_the_manifest_records_the_structured_execution_facts(self) -> None:
        manifest = self.manifest_for(GENERATED_TRANSFORMATION_ROLE)

        self.assertEqual(1, manifest["maven"]["exit_code"])
        self.assertFalse(manifest["maven"]["timed_out"])
        self.assertEqual(2, manifest["surefire"]["tests"])
        self.assertEqual(1, manifest["surefire"]["failures"])
        self.assertEqual(0, manifest["surefire"]["errors"])
        self.assertEqual("assertion_failure", manifest["classification"]["failure_stage"])


class MissingReportsTests(unittest.TestCase):
    def test_absent_surefire_reports_are_recorded_as_absent_not_as_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            observation, evidence = harness.run(
                stdout="[ERROR] COMPILATION ERROR :",
                stderr="",
                exit_code=1,
                reports={},
            )
            path = record_observation(
                root / "observations",
                _suite(root),
                _transformation(root, "only.etl"),
                observation,
                evidence=evidence,
            )
            manifest = json.loads(
                (evidence_dir(path) / MANIFEST_FILENAME).read_text(encoding="utf-8")
            )

            self.assertFalse(manifest["surefire"]["present"])
            self.assertEqual([], manifest["surefire"]["reports"])
            # Not 0: an unknown count and a count of zero are different facts.
            self.assertIsNone(manifest["surefire"]["tests"])
            self.assertIsNone(manifest["surefire"]["failures"])
            self.assertIsNone(manifest["surefire"]["errors"])
            self.assertEqual((), archived_execution_evidence(path).surefire_reports)

    def test_the_stdout_that_explains_the_absence_is_still_archived(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            observation, evidence = harness.run(
                stdout="[ERROR] COMPILATION ERROR :",
                stderr="",
                exit_code=1,
                reports={},
            )
            path = record_observation(
                root / "observations",
                _suite(root),
                _transformation(root, "only.etl"),
                observation,
                evidence=evidence,
            )

            self.assertEqual(
                "[ERROR] COMPILATION ERROR :",
                (evidence_dir(path) / STDOUT_FILENAME).read_text(encoding="utf-8"),
            )


class VerdictIsUnaffectedTests(unittest.TestCase):
    def test_archiving_does_not_change_the_recorded_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            suite = _suite(root)
            transformation = _transformation(root, "only.etl")
            observation, evidence = harness.run(
                stdout="[INFO] run",
                stderr="",
                exit_code=1,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )

            without = record_observation(
                root / "without", suite, transformation, observation
            )
            with_evidence = record_observation(
                root / "with", suite, transformation, observation, evidence=evidence
            )

            self.assertEqual(
                json.loads(without.read_text(encoding="utf-8"))["observation"],
                json.loads(with_evidence.read_text(encoding="utf-8"))["observation"],
            )
            self.assertIsNone(archived_execution_evidence(without).directory)
            self.assertIsNotNone(archived_execution_evidence(with_evidence).directory)

    def test_an_archived_observation_still_reads_back_identically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            harness = _Harness(root)
            suite = _suite(root)
            transformation = _transformation(root, "only.etl")
            observation, evidence = harness.run(
                stdout="[INFO] run",
                stderr="",
                exit_code=0,
                reports={"TEST-GeneratedTest.xml": REPORT_XML},
            )
            observations = root / "observations"
            record_observation(
                observations, suite, transformation, observation, evidence=evidence
            )

            # The evidence directory sits beside the observation and must not
            # disturb reading it back.
            self.assertEqual(
                observation, read_observation(observations, suite, transformation)
            )
            self.assertTrue(
                evidence_dir(observation_path(observations, suite)).is_dir()
            )


if __name__ == "__main__":
    unittest.main()
