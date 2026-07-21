from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_SCRIPTS = REPO_ROOT / "Transformation_Validation" / "scripts" / "etl"
TEST_GENERATION_SCRIPTS = REPO_ROOT / "Test_Generation" / "scripts"
for import_root in (VALIDATION_SCRIPTS, TEST_GENERATION_SCRIPTS):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from transformation_validation.artifacts import archive_result
from transformation_validation.discovery import (
    discover_transformations,
    discover_validated_suites,
    match_pairs,
)
from transformation_validation.models import TransformationValidationResult
from transformation_validation.results import write_results
from transformation_validation.runner import failure_stage


class DiscoveryTests(unittest.TestCase):
    def test_matches_only_same_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            validated_root = root / "generated_tests" / "etl"
            suite = validated_root / "Tree2Graph" / "validated" / "gpt-5" / "few_shot" / "suite_001"
            suite.mkdir(parents=True)
            transformations_root = root / "resources"
            tree = transformations_root / "gpt-5" / "grammar" / "Tree2Graph.etl"
            tree.parent.mkdir(parents=True)
            tree.write_text("rule Tree2Node {}\n", encoding="utf-8")
            other = transformations_root / "gpt-5" / "grammar" / "OO2DB.etl"
            other.write_text("rule Class2Table {}\n", encoding="utf-8")

            suites = discover_validated_suites(validated_root)
            transformations = discover_transformations(transformations_root)
            pairs = match_pairs(suites, transformations)

            self.assertEqual(1, len(pairs))
            self.assertEqual("Tree2Graph", pairs[0].suite.task)
            self.assertEqual("grammar", pairs[0].transformation.strategy)


class ArtifactTests(unittest.TestCase):
    def test_failed_result_is_archived_with_repair_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            validated_root = root / "generated_tests" / "etl"
            suite_dir = validated_root / "Tree2Graph" / "validated" / "gpt-5" / "few_shot" / "suite_001"
            (suite_dir / "models").mkdir(parents=True)
            (suite_dir / "GeneratedTest.java").write_text("class GeneratedTest {}\n", encoding="utf-8")
            (suite_dir / "models" / "input.model").write_text("<model/>\n", encoding="utf-8")
            transformations_root = root / "resources"
            transformation_path = transformations_root / "gpt-5" / "grammar" / "Tree2Graph.etl"
            transformation_path.parent.mkdir(parents=True)
            transformation_path.write_text("invalid ETL\n", encoding="utf-8")

            pair = match_pairs(
                discover_validated_suites(validated_root),
                discover_transformations(transformations_root),
            )[0]
            result = TransformationValidationResult(
                pair=pair,
                run_id="run_test",
                transformation_sha256="transform-hash",
                suite_sha256="suite-hash",
                status="failed",
                failure_stage="transformation_parse",
                compiles=True,
                executes=True,
                tests_pass=False,
                maven_exit_code=1,
                timed_out=False,
                error_summary="parse error",
                maven_output="full error",
            )

            archived = archive_result(result, root / "artifacts")
            bundle = root / archived.artifact_dir if not Path(archived.artifact_dir).is_absolute() else Path(archived.artifact_dir)
            self.assertTrue((bundle / "transformation.etl").is_file())
            self.assertTrue((bundle / "suite" / "GeneratedTest.java").is_file())
            self.assertTrue((bundle / "result.json").is_file())
            self.assertTrue((bundle / "repair_request.md").is_file())


class FailureStageTests(unittest.TestCase):
    def test_classifies_etl_parse_error(self) -> None:
        self.assertEqual(
            "transformation_parse",
            failure_stage("RuntimeException: ETL parse errors: unexpected token", True, True, False),
        )

    def test_classifies_assertion_failure(self) -> None:
        self.assertEqual("test_failure", failure_stage("Tests run: 3, Failures: 1", True, True, False))


class ReadableReportTests(unittest.TestCase):
    def test_writes_labelled_pass_fail_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            validated_root = root / "generated_tests" / "etl"
            suite_dir = validated_root / "Tree2Graph" / "validated" / "gpt-5" / "few_shot" / "suite_001"
            suite_dir.mkdir(parents=True)
            transformations_root = root / "transformations"
            transformation_path = transformations_root / "claude-sonnet-4" / "grammar" / "Tree2Graph.etl"
            transformation_path.parent.mkdir(parents=True)
            transformation_path.write_text("rule Tree2Graph {}\n", encoding="utf-8")
            pair = match_pairs(
                discover_validated_suites(validated_root),
                discover_transformations(transformations_root),
            )[0]
            result = TransformationValidationResult(
                pair=pair,
                run_id="run_test",
                transformation_sha256="transform-hash",
                suite_sha256="suite-hash",
                status="failed",
                failure_stage="test_failure",
                compiles=True,
                executes=True,
                tests_pass=False,
                maven_exit_code=1,
                timed_out=False,
                error_summary="Expected Graph but found Tree.",
                maven_output="full error",
                artifact_dir="artifacts/failed",
            )

            paths = write_results([result], root / "results", append=False)

            report_path = (
                root / "results" / "Tree2Graph" / "generated_transformation_validation_report.csv"
            ).resolve()
            self.assertIn(report_path, paths)
            report = report_path.read_text(encoding="utf-8")
            self.assertIn("=== Task: Tree2Graph | Transformation: claude-sonnet-4/grammar", report)
            self.assertIn("Test result,FAIL", report)
            self.assertIn("Compilation,PASS", report)
            self.assertIn("Test execution,PASS", report)
            self.assertIn("Explanation,Expected Graph but found Tree.", report)
            self.assertIn("--- End of evaluation ---", report)


if __name__ == "__main__":
    unittest.main()
