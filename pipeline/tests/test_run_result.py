"""Where a run ended, recorded once, beside the run it describes.

The terminal decision — completed_with_failures because refinement was disabled,
incomplete because a diagnosis set never finished — lived only in the n8n
execution. Reading a finished run therefore meant reconstructing it from the
event log, from which artifacts are missing, and from the routing rules. These
tests pin that the run says it itself, and that what it says about its stages
comes from the attempts it recorded rather than from the caller.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl import run_store
from llm4mtl.provenance import build_provenance
from llm4mtl.run_store.results import aggregate_classification
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.stage_service.app import app

IDENTITY = {
    "language": "etl",
    "task": "Tree2Graph",
    "transformation_model": "gpt-5",
    "test_generation_model": "gpt-5",
    "transformation_strategy": "few_shots_AND_grammar",
    "test_generation_strategy": "few_shot",
}
TERMINAL = {
    "status": "completed_with_failures",
    "terminal_state": "DIAGNOSED_TRANSFORMATION_DEFECT:REFINEMENT_LIMIT_REACHED",
    "run_mode": "full",
    "refinement_iterations_used": 0,
    "refinement_iterations_allowed": 0,
    "suite_id": "result-1_000",
}


class AggregateClassificationTests(unittest.TestCase):

    def test_the_aggregate_is_conservative_and_never_a_majority_vote(self) -> None:
        self.assertIsNone(aggregate_classification([]))
        self.assertEqual(
            "TRANSFORMATION_DEFECT",
            aggregate_classification(["TRANSFORMATION_DEFECT"] * 3),
        )
        # One of each kind means the evidence points at both artefacts, and
        # three-to-one is still both.
        self.assertEqual(
            "AMBIGUOUS",
            aggregate_classification(["TRANSFORMATION_DEFECT"] * 3 + ["TEST_DEFECT"]),
        )
        self.assertEqual(
            "AMBIGUOUS",
            aggregate_classification(["TRANSFORMATION_DEFECT", "AMBIGUOUS"]),
        )


class RunResultServiceTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.runs_root = self.root / "runs"
        self.diagnoses = self.root / "diagnoses"
        self.addCleanup(lambda: shutil.rmtree(self.diagnoses, ignore_errors=True))
        for target, value in (
            ("_runs_root", self.runs_root),
            ("_diagnoses_root", self.diagnoses),
        ):
            patcher = patch(f"llm4mtl.stage_service.app.{target}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.client.post("/runs", json={**IDENTITY, "run_id": "result-1"})
        self.paths = run_store.open_run(self.runs_root, "result-1")

    def _record_stage(self, stage: str, status: str, outcome_code: str) -> None:
        run_store.record_attempt(
            self.paths,
            stage,
            {
                "schema_version": "2.0",
                "stage": stage,
                "status": status,
                "outcome_code": outcome_code,
                "counts": {},
                "artifacts": {},
            },
        )

    def _record_diagnosis(self, classification: str) -> None:
        response = self.client.post(
            "/runs/result-1/diagnoses",
            json={
                "schema_version": "1.0",
                "classification": classification,
                "rationale": "recorded by a test",
                "provider": "openai",
                "model": "gpt-5",
                "created_at": "2026-08-20T13:56:00+00:00",
            },
        )
        self.assertEqual(200, response.status_code, response.text)

    def test_the_result_states_the_ending_and_reads_the_rest_off_the_run(self) -> None:
        self._record_stage("syntax-validation", "passed", "SYNTAX_VALID")
        self._record_stage("execution", "failed", "SEMANTIC_EXECUTION_FAILED")
        for _ in range(3):
            self._record_diagnosis("TRANSFORMATION_DEFECT")

        response = self.client.post("/runs/result-1/result", json=TERMINAL)

        self.assertEqual(200, response.status_code, response.text)
        result = response.json()
        self.assertEqual("completed_with_failures", result["status"])
        # The reason string is split where the workflow already splits it: what
        # the run ended as, and what stopped it there.
        self.assertEqual("DIAGNOSED_TRANSFORMATION_DEFECT", result["outcome_code"])
        self.assertEqual("REFINEMENT_LIMIT_REACHED", result["terminal_reason"])
        self.assertEqual(TERMINAL["terminal_state"], result["terminal_state"])
        self.assertEqual("passed", result["syntax_status"])
        self.assertEqual("failed", result["semantic_status"])
        # One defect, three affected cases, three records: the file states how
        # many verdicts there were rather than implying three defects.
        self.assertEqual("TRANSFORMATION_DEFECT", result["diagnosis"])
        self.assertEqual(3, result["diagnosis_records"])
        self.assertEqual(
            ["TRANSFORMATION_DEFECT"] * 3, result["diagnosis_classifications"]
        )
        self.assertEqual(
            "SEMANTIC_EXECUTION_FAILED", result["stages"]["execution"]["outcome_code"]
        )
        self.assertEqual(0, result["refinement_iterations_allowed"])

        stored = read_json(self.paths.root / "result.json")
        self.assertEqual(result, stored)
        self.assertIn(
            "run_finished",
            [event["event"] for event in run_store.read_events(self.paths)],
        )

    def test_a_stage_that_never_ran_is_not_run_rather_than_passing(self) -> None:
        response = self.client.post(
            "/runs/result-1/result",
            json={
                **TERMINAL,
                "status": "incomplete",
                "terminal_state": "ALL_PIPELINE_STAGES_DISABLED",
            },
        )

        result = response.json()
        self.assertEqual("not_run", result["syntax_status"])
        self.assertEqual("not_run", result["semantic_status"])
        self.assertIsNone(result["diagnosis"])
        self.assertIsNone(result["terminal_reason"])
        self.assertEqual({}, result["stages"])

    def test_orchestration_error_records_recoverable_terminal_context(self) -> None:
        response = self.client.post(
            "/runs/result-1/result",
            json={
                **TERMINAL,
                "status": "failed",
                "terminal_state": "ORCHESTRATION_ERROR:prepare_refinement",
                "failed_component": "prepare_refinement",
                "last_completed_stage": "execution",
                "test_iteration": 0,
                "transformation_iteration": 1,
            },
        )

        self.assertEqual(200, response.status_code, response.text)
        result = response.json()
        self.assertEqual("ORCHESTRATION_ERROR", result["outcome_code"])
        self.assertEqual("prepare_refinement", result["failed_component"])
        self.assertEqual("execution", result["last_completed_stage"])
        self.assertEqual(0, result["test_iteration"])
        self.assertEqual(1, result["transformation_iteration"])

    def test_the_same_ending_may_be_reported_twice_and_a_different_one_may_not(
        self,
    ) -> None:
        """An n8n retry re-posts; a second, different ending is a conflict."""
        first = self.client.post("/runs/result-1/result", json=TERMINAL)
        again = self.client.post("/runs/result-1/result", json=TERMINAL)

        self.assertEqual(200, again.status_code)
        self.assertEqual(first.json(), again.json())

        conflicting = self.client.post(
            "/runs/result-1/result",
            json={
                **TERMINAL,
                "status": "completed",
                "terminal_state": "SEMANTIC_PASSED",
            },
        )
        self.assertEqual(409, conflicting.status_code)
        self.assertEqual(
            first.json()["terminal_state"],
            read_json(self.paths.root / "result.json")["terminal_state"],
        )

    def test_a_result_for_an_unknown_run_is_refused(self) -> None:
        self.assertEqual(
            404, self.client.post("/runs/absent/result", json=TERMINAL).status_code
        )

    def test_the_caller_cannot_state_what_the_stages_observed(self) -> None:
        """Only the terminal decision is representable in the request.

        A stale workflow that tried to report its own syntax_status would be
        reporting a fact the run already recorded, and the two could disagree.
        """
        response = self.client.post(
            "/runs/result-1/result", json={**TERMINAL, "syntax_status": "passed"}
        )
        self.assertEqual(422, response.status_code)


class RunResultWriterTests(unittest.TestCase):
    """The writer keeps working on a run directory nobody served over HTTP."""

    def test_a_result_can_be_recorded_directly_from_the_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paths = run_store.create_run(
                root / "runs",
                "direct-1",
                {
                    **IDENTITY,
                    "seed": 1,
                    "pipeline_variant": "full",
                    "provenance": build_provenance(
                        IDENTITY["language"], IDENTITY["task"]
                    ),
                },
            )
            write_json(
                root / "diagnoses" / "direct-1" / "attempt-001" / "diagnosis.json",
                {"classification": "TEST_DEFECT"},
            )

            result = run_store.record_result(
                paths,
                {
                    "status": "completed_with_failures",
                    "terminal_state": "DIAGNOSED_TEST_DEFECT",
                    "run_mode": "full",
                    "refinement_iterations_used": 1,
                    "refinement_iterations_allowed": 2,
                },
                root / "diagnoses",
            )

            self.assertEqual("TEST_DEFECT", result["diagnosis"])
            self.assertIsNone(result["terminal_reason"])
            self.assertEqual(1, result["refinement_iterations_used"])
            self.assertEqual(result, run_store.read_result(paths))


if __name__ == "__main__":
    unittest.main()
