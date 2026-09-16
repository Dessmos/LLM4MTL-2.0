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
        previous.write_text(
            "rule Broken { transform s : Tree!Tree to t : Graph!Graph {} }\n",
            encoding="utf-8",
        )
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
            run_diagnoses=self.root / "diagnoses" / self.paths.root.name,
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
            self.paths.generation_iteration_dir("transformation-generation", 1).is_dir()
        )

    def test_a_custom_task_prompt_is_what_generation_and_refinement_cite(self) -> None:
        """One specification per run: the prompt it was created with.

        A custom task borrows Tree2Graph's contract but not its frozen prompt,
        so neither the generation record nor the refinement may fall back to
        that frozen text.
        """
        prompt = "Flatten every tree into one graph node per leaf.\n"
        paths = run_store.create_run(
            self.root / "runs",
            "custom-1",
            {
                **IDENTITY,
                "provenance": build_provenance(
                    "etl", "Tree2Graph", custom_task_prompt=prompt
                ),
            },
            task_prompt=prompt,
        )
        manifest = run_store.read_manifest(paths)
        assert manifest is not None
        initial = paths.generation_response(
            "transformation-generation", 0, "Tree2Graph.etl"
        )
        initial.parent.mkdir(parents=True, exist_ok=True)
        initial.write_text("rule Broken { }\n", encoding="utf-8")

        record = run_store.record_generation(
            paths,
            manifest,
            artifact_type="transformation",
            iteration=0,
            purpose="initial",
            provider="openai",
            model="gpt-5",
            strategy="grammar",
        )
        self.assertEqual("task-prompt.md", record["prompt"]["path"])
        self.assertEqual(
            manifest["provenance"]["input_hashes"]["task_prompt"],
            record["prompt"]["sha256"],
        )

        run_store.record_attempt(
            paths,
            "syntax-validation",
            {
                "schema_version": "2.0",
                "stage": "syntax-validation",
                "status": "failed",
                "outcome_code": "SYNTAX_INVALID",
                "counts": {"failed": 1},
                "artifacts": {},
            },
            evidence={"details": {"parser_diagnostics": ["line 1: unexpected token"]}},
        )
        prepared = run_store.prepare_refinement(
            paths,
            manifest,
            artifact_type="transformation",
            iteration=1,
            previous_iteration=0,
            provider="google",
            model="gemini-2.5-pro",
            reason="SYNTAX_INVALID",
            run_diagnoses=self.root / "diagnoses" / paths.root.name,
        )
        request = read_json(paths.root / prepared["request_path"])
        rendered = (paths.root / request["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn("Flatten every tree", rendered)
        frozen_prompt = (
            Path(__file__).resolve().parents[2]
            / "prompt_assets"
            / "task_prompts"
            / "etl"
            / "Tree2Graph.txt"
        )
        first_frozen_line = frozen_prompt.read_text(encoding="utf-8").strip().splitlines()[0]
        self.assertNotIn(first_frozen_line, rendered)

    def test_reference_refinement_carries_the_assertion_the_reference_rejected(
        self,
    ) -> None:
        """Reference validation records its verdict as a suite observation, so the
        failure slot used to arrive empty and the prompt said only that the suite
        was REFERENCE_INVALID. Every retry then reproduced its own input.
        """
        previous = self.paths.generation_response(
            "semantic-test-generation", 0, "Tree2Graph.md"
        )
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_text("```json file=semantic_cases.json\n{}\n```\n", encoding="utf-8")
        write_json(
            self.paths.root
            / "observations"
            / "Tree2Graph"
            / "gpt-5"
            / "few_shot"
            / f"{self.paths.root.name}_000"
            / "suite_execution.json",
            {
                "schema_version": "2.0",
                "language": "etl",
                "task": "Tree2Graph",
                "llm": "gpt-5",
                "strategy": "few_shot",
                "suite_id": f"{self.paths.root.name}_000",
                "inputs": {
                    "suite": {"path": "suite", "sha256": "0" * 64, "role": "generated_suite"},
                    "transformation": {
                        "path": "benchmark/tasks/etl/references/Tree2Graph.etl",
                        "sha256": "1" * 64,
                        "role": "reference_transformation",
                    },
                },
                "observation": {
                    "compiled": True,
                    "tests_discovered": True,
                    "models_loaded": True,
                    "engine_started": True,
                    "assertions_evaluated": True,
                    "assertions_passed": False,
                    "timed_out": False,
                    "maven_exit_code": 1,
                    "failure_stage": "assertion_failure",
                    "error_summary": "singleRoot: count for Graph::Node ==> expected: <2> but was: <3>",
                    "technically_executable": True,
                    "reference_valid": False,
                },
            },
        )
        for stage, status, outcome in (
            ("technical-validation", "passed", "TECH_VALID"),
            ("reference-validation", "failed", "REFERENCE_VALIDATION_FAILED"),
        ):
            run_store.record_attempt(
                self.paths,
                stage,
                {
                    "schema_version": "2.0",
                    "stage": stage,
                    "status": status,
                    "outcome_code": outcome,
                    "counts": {"selected": 1},
                    "artifacts": {},
                },
                evidence={"details": {"verdicts": []}},
            )

        prepared = run_store.prepare_refinement(
            self.paths,
            self.manifest,
            artifact_type="semantic-test",
            iteration=1,
            previous_iteration=0,
            provider="openai",
            model="gpt-5.3-codex",
            reason="REFERENCE_VALIDATION_FAILED",
            run_diagnoses=self.root / "diagnoses" / self.paths.root.name,
        )

        request = read_json(self.paths.root / prepared["request_path"])
        prompt = (self.paths.root / request["prompt_file"]).read_text(encoding="utf-8")
        reports = request["feedback"]["failure_reports"]
        self.assertEqual("reference", request["feedback"]["source"])
        self.assertEqual(1, len(reports))
        self.assertEqual("assertion_failure", reports[0]["failure"]["failure_stage"])
        self.assertIn("expected: <2> but was: <3>", prompt)

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
            run_diagnoses=self.root / "diagnoses" / self.paths.root.name,
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
        self.assertEqual(
            first["output_artifact"]["sha256"], second["input_artifact"]["sha256"]
        )
        self.assertNotEqual(
            second["input_artifact"]["sha256"], second["output_artifact"]["sha256"]
        )
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
                run_diagnoses=self.root / "diagnoses" / self.paths.root.name,
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
        run_diagnoses = self.root / "diagnoses" / self.paths.root.name
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
                run_diagnoses,
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
            run_diagnoses=run_diagnoses,
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
            self.paths.generation_iteration_dir("semantic-test-generation", 1).is_dir()
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


class CustomTaskRefinementContextTests(unittest.TestCase):
    """What a refinement prompt restates for a run that supplied its metamodel.

    The generation being refined was produced from the metamodel the run was
    created with. A prompt that restated a contract's metamodels instead would
    be asking about a different task, so refinement re-reads the run's own copy.
    """

    METAMODEL = "class Tree { children: Tree[] }\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.paths = run_store.create_run(
            self.root / "runs",
            "custom-1",
            {
                **IDENTITY,
                "task": "TreeFlattening",
                "pipeline_variant": "full:custom-task:TreeFlattening",
                "provenance": build_provenance(
                    "etl",
                    "TreeFlattening",
                    custom_task_prompt="Flatten every tree.\n",
                    custom_task_metamodel=self.METAMODEL,
                ),
            },
            task_prompt="Flatten every tree.\n",
            metamodel=self.METAMODEL,
        )
        self.manifest = run_store.read_manifest(self.paths)
        assert self.manifest is not None

    def test_refinement_restates_the_metamodel_the_run_was_created_with(self) -> None:
        previous = self.paths.generation_response(
            "transformation-generation", 0, "TreeFlattening.etl"
        )
        previous.parent.mkdir(parents=True, exist_ok=True)
        previous.write_text("rule Flatten {}\n", encoding="utf-8")
        # The syntax failure this refinement answers.
        attempt = self.paths.stage_attempt_dir("syntax-validation", 1)
        attempt.mkdir(parents=True, exist_ok=True)
        write_json(
            attempt / "result.json",
            {"status": "failed", "outcome_code": "SYNTAX_INVALID", "counts": {}},
        )

        prepared = run_store.prepare_refinement(
            self.paths,
            self.manifest,
            artifact_type="transformation",
            iteration=1,
            previous_iteration=0,
            provider="openai",
            model="gpt-5",
            reason="SYNTAX_INVALID",
            run_diagnoses=self.paths.root / "diagnosis",
        )
        request = read_json(
            self.paths.refinement_dir("transformation", 1) / "request.json"
        )
        context = request["original_task_context"]
        self.assertEqual(1, len(context["metamodels"]))
        self.assertEqual(self.METAMODEL, context["metamodels"][0]["content"])
        self.assertIn("metamodel.txt", context["metamodels"][0]["path"])
        # The prompt the LLM is handed says the same thing the request records.
        prompt = (self.paths.root / prepared["prompt_file"]).read_text(encoding="utf-8")
        self.assertIn(self.METAMODEL.strip(), prompt)
        self.assertNotIn("Tree2Graph", prompt)


if __name__ == "__main__":
    unittest.main()
