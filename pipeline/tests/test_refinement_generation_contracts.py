from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm4mtl import run_store
from llm4mtl.artifact_schemas import ArtifactSchemaError
from llm4mtl.provenance import build_provenance
from llm4mtl.semantic_tests.diagnosis_preparation import (
    DiagnosisPreparationError,
    read_diagnosis_queue,
)
from llm4mtl.serialization.json_io import read_json, write_json


IDENTITY = {
    "language": "etl",
    "task": "Tree2Graph",
    "transformation_model": "gpt-5",
    "test_generation_model": "gpt-5",
    "transformation_strategy": "few_shots_AND_grammar",
    "test_generation_strategy": "few_shot",
    "seed": 1,
    "pipeline_variant": "full",
}


class RefinementGenerationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.paths = run_store.create_run(
            self.root / "runs",
            "feedback-1",
            {
                **IDENTITY,
                "provenance": build_provenance("etl", "Tree2Graph"),
            },
        )
        self.manifest = run_store.read_manifest(self.paths)
        assert self.manifest is not None

    def _write_diagnosis_index(
        self,
        attempt: int,
        *,
        report_run_id: str | None = None,
        report_attempt: int | None = None,
        report_path: Path | None = None,
        corrupt_report: bool = False,
        create_report: bool = True,
    ) -> tuple[Path, Path]:
        reports_dir = (
            self.paths.root
            / "diagnosis"
            / "execution"
            / f"attempt-{attempt:03d}"
            / "reports"
        )
        selected_report = report_path or reports_dir / "failure.json"
        if create_report:
            if corrupt_report:
                write_json(selected_report, {"invalid": True})
            else:
                write_json(
                    selected_report,
                    {
                        "schema_version": "1.0",
                        "report_type": "semantic_test_case_failure",
                        "identity": {
                            "run_id": report_run_id or self.paths.root.name,
                            "task_id": "Tree2Graph",
                            "language": "etl",
                            "attempt": report_attempt or attempt,
                        },
                        "task_context": {},
                        "test_case_result": {},
                        "source_diagnosis": {
                            "eligible": True,
                            "reason": f"attempt-{attempt}-feedback",
                            "evidence_bundle": {},
                            "allowed_classifications": [
                                "transformation_defect",
                                "test_defect",
                                "ambiguous",
                            ],
                            "required_result_fields": [],
                        },
                    },
                )
        index_path = reports_dir.parent / "index.json"
        write_json(
            index_path,
            {
                "schema_version": "1.0",
                "run_id": self.paths.root.name,
                "stage": "execution",
                "attempt": attempt,
                "prepared_at": "2026-08-21T12:00:00+00:00",
                "execution_evidence": None,
                "syntax_evidence": None,
                "counts": {
                    "failed_pairs": 1,
                    "reports_created": 1,
                    "reports_refused": 0,
                    "pair_level_reports": 0,
                    "diagnosis_eligible": 1,
                    "pairs_without_reports": 0,
                },
                "pairs": [
                    {
                        "suite": "suite",
                        "transformation": "transformation",
                        "observation": "observation",
                        "failure_stage": "test",
                        "reports": [
                            {
                                "status": "created",
                                "eligible": True,
                                "report": str(selected_report.resolve()),
                                "test_case_id": "case-1",
                                "assertion_id": "assertion-1",
                            }
                        ],
                        "skipped": [],
                    }
                ],
            },
        )
        return index_path, selected_report

    def test_transformation_refinement_contains_previous_source_and_parser_feedback(
        self,
    ) -> None:
        previous = self.paths.generation_response(
            "transformation-generation", 0, "Tree2Graph.etl"
        )
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_text("rule Broken { transform s : Tree!Tree to t : Graph!Graph {} }\n", encoding="utf-8")
        run_store.record_attempt(
            self.paths,
            "syntax-validation",
            {
                "schema_version": "2.0",
                "stage": "syntax-validation",
                "status": "failed",
                "outcome_code": "SYNTAX_INVALID",
                "counts": {"failed": 1},
                "artifacts": {},
            },
            evidence={
                "details": {
                    "parser_diagnostics": ["line 1: unexpected token transform"]
                }
            },
        )

        prepared = run_store.prepare_refinement(
            self.paths,
            self.manifest,
            artifact_type="transformation",
            iteration=1,
            previous_iteration=0,
            provider="google",
            model="gemini-2.5-pro",
            reason="SYNTAX_INVALID",
            diagnoses_root=self.root / "diagnoses",
        )

        request = read_json(self.paths.root / prepared["request_path"])
        prompt = (self.paths.root / request["prompt_file"]).read_text(encoding="utf-8")
        self.assertEqual("syntax", request["feedback"]["source"])
        self.assertIsNone(request["execution_attempt"])
        self.assertEqual("google", request["provider"])
        self.assertIn("rule Broken", prompt)
        self.assertIn("unexpected token transform", prompt)
        self.assertIn("Preserve behavior unrelated", prompt)
        self.assertIn("prompt_assets/transformations/few_shot/etl/Examples.txt", prompt)
        self.assertTrue(
            self.paths.generation_iteration_dir(
                "transformation-generation", 1
            ).is_dir()
        )

    def test_generation_record_uses_actual_n8n_model_and_links_both_iterations(
        self,
    ) -> None:
        initial = self.paths.generation_response(
            "transformation-generation", 0, "Tree2Graph.etl"
        )
        initial.parent.mkdir(parents=True, exist_ok=True)
        initial.write_text("initial transformation\n", encoding="utf-8")
        first = run_store.record_generation(
            self.paths,
            self.manifest,
            artifact_type="transformation",
            iteration=0,
            purpose="initial",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            strategy="few_shots_AND_grammar",
        )
        self.assertEqual("anthropic", first["provider"])
        self.assertEqual("claude-sonnet-4-20250514", first["model"])
        self.assertNotEqual(self.manifest["transformation_model"], first["model"])

        run_store.record_attempt(
            self.paths,
            "syntax-validation",
            {
                "schema_version": "2.0",
                "stage": "syntax-validation",
                "status": "failed",
                "outcome_code": "SYNTAX_INVALID",
            },
            evidence={"details": {"parser_diagnostics": ["bad syntax"]}},
        )
        run_store.prepare_refinement(
            self.paths,
            self.manifest,
            artifact_type="transformation",
            iteration=1,
            previous_iteration=0,
            provider="google",
            model="gemini-2.5-pro",
            reason="SYNTAX_INVALID",
            diagnoses_root=self.root / "diagnoses",
        )
        refined = self.paths.generation_response(
            "transformation-generation", 1, "Tree2Graph.etl"
        )
        refined.parent.mkdir(parents=True, exist_ok=True)
        refined.write_text("corrected transformation\n", encoding="utf-8")

        second = run_store.record_generation(
            self.paths,
            self.manifest,
            artifact_type="transformation",
            iteration=1,
            purpose="syntax_refinement",
            provider="google",
            model="gemini-2.5-pro",
            strategy="few_shots_AND_grammar",
        )
        self.assertEqual(0, second["input_artifact_iteration"])
        self.assertEqual(1, second["created_artifact_iteration"])
        self.assertEqual(first["output_artifact"]["sha256"], second["input_artifact"]["sha256"])
        self.assertNotEqual(second["input_artifact"]["sha256"], second["output_artifact"]["sha256"])
        self.assertIsNotNone(second["refinement_request"])

    def test_refinement_stops_before_prompt_handoff_when_response_path_is_blocked(
        self,
    ) -> None:
        previous = self.paths.generation_response(
            "transformation-generation", 0, "Tree2Graph.etl"
        )
        previous.write_text("broken transformation\n", encoding="utf-8")
        run_store.record_attempt(
            self.paths,
            "syntax-validation",
            {
                "schema_version": "2.0",
                "stage": "syntax-validation",
                "status": "failed",
                "outcome_code": "SYNTAX_INVALID",
            },
            evidence={"details": {"parser_diagnostics": ["bad syntax"]}},
        )
        response_directory = self.paths.generation_iteration_dir(
            "transformation-generation", 1
        )
        response_directory.write_text("blocks directory creation\n", encoding="utf-8")

        with self.assertRaisesRegex(
            run_store.RefinementPreparationError,
            "cannot prepare transformation generation directory",
        ):
            run_store.prepare_refinement(
                self.paths,
                self.manifest,
                artifact_type="transformation",
                iteration=1,
                previous_iteration=0,
                provider="google",
                model="gemini-2.5-pro",
                reason="SYNTAX_INVALID",
                diagnoses_root=self.root / "diagnoses",
            )

        refinement_directory = self.paths.refinement_dir("transformation", 1)
        self.assertFalse((refinement_directory / "prompt.md").exists())
        self.assertFalse((refinement_directory / "request.json").exists())

    def test_semantic_refinement_uses_only_the_selected_execution_attempt(self) -> None:
        previous = self.paths.generation_response(
            "semantic-test-generation", 0, "Tree2Graph.md"
        )
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_text("Suite0 semantic cases\n", encoding="utf-8")
        for attempt in (1, 2):
            recorded = run_store.record_attempt(
                self.paths,
                "execution",
                {
                    "schema_version": "2.0",
                    "status": "failed",
                    "outcome_code": "SEMANTIC_EXECUTION_FAILED",
                },
                evidence={"details": {"marker": f"execution-{attempt}"}},
            )
            self.assertEqual(attempt, recorded)
            self._write_diagnosis_index(attempt)
        diagnoses_root = self.root / "diagnoses"
        for attempt, classification, rationale in (
            (1, "TRANSFORMATION_DEFECT", "OLD_TRANSFORMATION_DIAGNOSIS"),
            (2, "TEST_DEFECT", "CURRENT_TEST_DIAGNOSIS"),
        ):
            run_store.record_diagnosis(
                self.paths,
                {
                    "schema_version": "1.0",
                    "classification": classification,
                    "evidence_ref": (
                        f"diagnosis/execution/attempt-{attempt:03d}/reports/failure.json"
                    ),
                    "rationale": rationale,
                    "provider": "openai",
                    "model": "gpt-5",
                    "created_at": "2026-08-21T12:00:00+00:00",
                },
                diagnoses_root,
            )

        prepared = run_store.prepare_refinement(
            self.paths,
            self.manifest,
            artifact_type="semantic-test",
            iteration=1,
            previous_iteration=0,
            provider="google",
            model="gemini-2.5-pro",
            reason="DIAGNOSED_TEST_DEFECT",
            diagnoses_root=diagnoses_root,
            execution_attempt=2,
        )

        request = read_json(self.paths.root / prepared["request_path"])
        prompt = (self.paths.root / request["prompt_file"]).read_text(encoding="utf-8")
        self.assertEqual(2, request["execution_attempt"])
        self.assertEqual(
            [2],
            [
                report["identity"]["attempt"]
                for report in request["feedback"]["failure_reports"]
            ],
        )
        self.assertEqual(
            ["TEST_DEFECT"],
            [
                diagnosis["classification"]
                for diagnosis in request["feedback"]["diagnoses"]
            ],
        )
        self.assertIn("CURRENT_TEST_DIAGNOSIS", prompt)
        self.assertIn("Suite0 semantic cases", prompt)
        self.assertIn("Repair the previous generated semantic test", prompt)
        self.assertNotIn("OLD_TRANSFORMATION_DIAGNOSIS", prompt)
        self.assertNotIn("attempt-1-feedback", prompt)
        self.assertTrue(
            self.paths.generation_iteration_dir(
                "semantic-test-generation", 1
            ).is_dir()
        )

    def test_diagnosis_resume_refuses_an_index_outside_its_schema(self) -> None:
        index_path, report_path = self._write_diagnosis_index(1)
        queue = read_diagnosis_queue(self.paths.root, 1)
        self.assertEqual(
            str(report_path.resolve()),
            queue["eligible_reports"][0]["failure_report_path"],
        )

        invalid = read_json(index_path)
        invalid["workflow_route"] = "diagnose"
        write_json(index_path, invalid)
        with self.assertRaises(ArtifactSchemaError):
            read_diagnosis_queue(self.paths.root, 1)

    def test_diagnosis_resume_rejects_a_missing_report(self) -> None:
        self._write_diagnosis_index(1, create_report=False)
        with self.assertRaisesRegex(DiagnosisPreparationError, "missing"):
            read_diagnosis_queue(self.paths.root, 1)

    def test_diagnosis_resume_rejects_a_corrupt_report(self) -> None:
        self._write_diagnosis_index(1, corrupt_report=True)
        with self.assertRaisesRegex(DiagnosisPreparationError, "invalid"):
            read_diagnosis_queue(self.paths.root, 1)

    def test_diagnosis_resume_rejects_a_cross_run_report(self) -> None:
        other_report = self.root / "runs" / "other-run" / "reports" / "failure.json"
        self._write_diagnosis_index(
            1,
            report_run_id="other-run",
            report_path=other_report,
        )
        with self.assertRaisesRegex(DiagnosisPreparationError, "outside run"):
            read_diagnosis_queue(self.paths.root, 1)

    def test_diagnosis_resume_rejects_a_wrong_attempt_report(self) -> None:
        self._write_diagnosis_index(1, report_attempt=2)
        with self.assertRaisesRegex(DiagnosisPreparationError, "identity"):
            read_diagnosis_queue(self.paths.root, 1)


if __name__ == "__main__":
    unittest.main()
