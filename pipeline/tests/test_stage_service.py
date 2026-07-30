from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl.experiment_runner.models import StageResult
from llm4mtl import run_store
from llm4mtl.provenance import build_provenance
from llm4mtl.serialization.json_io import read_json
from llm4mtl.stage_service.app import app

# A run is exactly one combination, so creating one states every identity axis.
IDENTITY = {
    "language": "etl",
    "task": "Tree2Graph",
    "transformation_model": "gpt-5",
    "test_generation_model": "gpt-5",
    "transformation_strategy": "grammar",
    "test_generation_strategy": "few_shot",
}


def run_payload(**overrides: object) -> dict[str, object]:
    return {**IDENTITY, **overrides}


class StageServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch(
            "llm4mtl.stage_service.app._runs_root", return_value=Path(self._tmp.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        self.client = TestClient(app)

    def test_create_run_then_read_manifest(self) -> None:
        created = self.client.post("/runs", json=run_payload(run_id="svc-1"))
        self.assertEqual(200, created.status_code)
        self.assertEqual({"run_id": "svc-1", "status": "initialized"}, created.json())

        fetched = self.client.get("/runs/svc-1")
        self.assertEqual(200, fetched.status_code)
        self.assertEqual("etl", fetched.json()["manifest"]["language"])
        self.assertEqual("svc-1", fetched.json()["manifest"]["run_id"])

    def test_prompt_inputs_are_resolved_through_the_task_contract(self) -> None:
        response = self.client.post(
            "/prompt-inputs/resolve",
            json={"language": "etl", "task": "Tree2Graph"},
        )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("Tree2Graph", body["task"])
        self.assertEqual(
            "benchmark/tasks/etl/references/Tree2Graph.etl",
            body["reference"]["path"],
        )
        self.assertEqual(
            [
                "benchmark/metamodels/etl/Graph.ecore",
                "benchmark/metamodels/etl/Tree.ecore",
            ],
            [metamodel["path"] for metamodel in body["metamodels"]],
        )
        self.assertNotIn("models", body["reference"])
        self.assertNotIn("contract", body)

    def test_prompt_input_resolution_does_not_fall_back_for_unknown_task(self) -> None:
        response = self.client.post(
            "/prompt-inputs/resolve",
            json={"language": "etl", "task": "does-not-exist"},
        )
        self.assertEqual(422, response.status_code)

    def test_create_run_refuses_to_replace_existing_manifest(self) -> None:
        first = self.client.post("/runs", json=run_payload(run_id="svc-immutable"))
        duplicate = self.client.post(
            "/runs", json=run_payload(run_id="svc-immutable", task="OO2DB")
        )
        self.assertEqual(200, first.status_code)
        self.assertEqual(409, duplicate.status_code)
        fetched = self.client.get("/runs/svc-immutable")
        self.assertEqual("Tree2Graph", fetched.json()["manifest"]["task"])

    def test_unknown_run_and_unknown_stage_return_404(self) -> None:
        self.assertEqual(404, self.client.post("/runs/nope/stages/extract", json={}).status_code)
        self.client.post("/runs", json=run_payload(run_id="svc-2", task="Tree2Graph"))
        self.assertEqual(404, self.client.post("/runs/svc-2/stages/not-a-stage", json={}).status_code)

    def test_malformed_or_escaping_run_ids_are_rejected(self) -> None:
        # A traversing id cannot arrive through the URL path (the router normalises
        # it away), so the containment check matters for ids supplied in a body.
        self.assertEqual(
            400,
            self.client.post("/runs", json=run_payload(run_id="../escape")).status_code,
        )
        # An id that does reach the handler is refused before it becomes a path.
        self.assertEqual(400, self.client.get("/runs/bad$id").status_code)
        self.assertEqual(
            400, self.client.post("/runs/bad$id/stages/extract", json={}).status_code
        )

    def test_a_run_must_fix_every_identity_axis(self) -> None:
        for missing in (
            "language",
            "task",
            "transformation_model",
            "test_generation_model",
            "transformation_strategy",
            "test_generation_strategy",
        ):
            with self.subTest(missing=missing):
                partial = {key: value for key, value in IDENTITY.items() if key != missing}
                response = self.client.post("/runs", json={**partial, "run_id": f"svc-no-{missing}"})
                self.assertEqual(422, response.status_code)

    def test_transport_models_reject_unknown_fields(self) -> None:
        created = self.client.post(
            "/runs",
            json=run_payload(run_id="svc-extra", unexpected_identity="value"),
        )
        self.assertEqual(422, created.status_code)

    def test_stage_request_cannot_carry_run_identity(self) -> None:
        self.client.post(
            "/runs",
            json=run_payload(run_id="svc-identity"),
        )

        wrong_task = self.client.post(
            "/runs/svc-identity/stages/extract", json={"tasks": ["OO2DB"]}
        )
        wrong_language = self.client.post(
            "/runs/svc-identity/stages/extract", json={"language": "atl"}
        )
        wrong_model = self.client.post(
            "/runs/svc-identity/stages/syntax-validation",
            json={"transformation_models": ["claude-sonnet-4"]},
        )

        self.assertEqual(422, wrong_task.status_code)
        self.assertEqual(422, wrong_language.status_code)
        self.assertEqual(422, wrong_model.status_code)
        # A rejected request records no evidence under the run.
        self.assertEqual(404, self.client.get("/runs/svc-identity/stages/extract").status_code)

    def test_stage_request_cannot_fill_an_identity_axis_recorded_as_null(self) -> None:
        run_store.create_run(
            Path(self._tmp.name),
            "svc-null-axis",
            {
                "language": "etl",
                "task": "Tree2Graph",
                "transformation_model": None,
                "test_generation_model": "gpt-5",
                "transformation_strategy": None,
                "test_generation_strategy": "few_shot",
                "seed": 1,
                "pipeline_variant": "full",
                "provenance": build_provenance("etl", "Tree2Graph"),
            },
        )

        response = self.client.post(
            "/runs/svc-null-axis/stages/syntax-validation",
            json={
                "transformation_models": ["gpt-5"],
                "transformation_strategies": ["grammar"],
            },
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual(
            404,
            self.client.get("/runs/svc-null-axis/stages/syntax-validation").status_code,
        )

    def test_stage_request_cannot_expand_to_all_tasks(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-one-task"))
        response = self.client.post(
            "/runs/svc-one-task/stages/extract",
            json={"all_tasks": True},
        )
        self.assertEqual(422, response.status_code)

    def test_stage_request_rejects_even_matching_identity_repetitions(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-agree"))
        response = self.client.post(
            "/runs/svc-agree/stages/extract", json={"language": "etl", "tasks": ["Tree2Graph"]}
        )
        self.assertEqual(422, response.status_code)

    def test_stage_request_rejects_a_traversing_suite_id(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-suite-id"))
        response = self.client.post(
            "/runs/svc-suite-id/stages/extract",
            json={"suite_id": "../../outside"},
        )
        self.assertEqual(422, response.status_code)

    def test_stage_returns_and_records_outcome_code(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-3"))
        with patch(
            "llm4mtl.stage_service.app._orchestrator.tests.extract",
            return_value=StageResult(
                "extraction",
                "infrastructure_error",
                {"infrastructure_errors": 1},
                {"error": "fixture failure"},
            ),
        ):
            response = self.client.post(
                "/runs/svc-3/stages/extract",
                json={},
            )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("extract", body["stage"])
        self.assertEqual("infrastructure_error", body["status"])
        self.assertEqual("INFRASTRUCTURE_ERROR", body["outcome_code"])
        self.assertEqual(1, body["attempt"])

        # The result is persisted and readable via GET (the latest recorded attempt).
        fetched = self.client.get("/runs/svc-3/stages/extract")
        self.assertEqual(200, fetched.status_code)
        self.assertEqual("INFRASTRUCTURE_ERROR", fetched.json()["outcome_code"])

    def test_stage_exception_is_recorded_as_infrastructure_error(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-4", task="Tree2Graph"))
        with patch(
            "llm4mtl.stage_service.app._orchestrator.tests.extract",
            side_effect=RuntimeError("adapter failed"),
        ):
            response = self.client.post(
                "/runs/svc-4/stages/extract", json={}
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("infrastructure_error", response.json()["status"])
        self.assertEqual("INFRASTRUCTURE_ERROR", response.json()["outcome_code"])
        self.assertEqual(1, response.json()["attempt"])

    def test_diagnosis_is_persisted_with_model_provenance(self) -> None:
        self.client.post("/runs", json=run_payload(run_id="svc-diagnosis", task="Tree2Graph"))
        payload = {
            "schema_version": "1.0",
            "classification": "TRANSFORMATION_DEFECT",
            "evidence_ref": "stages/execution/attempts/attempt-001/result.json",
            "rationale": "The generated transformation omitted the target node.",
            "provider": "openai",
            "model": "gpt-5",
            "created_at": "2026-07-29T12:00:00Z",
        }

        first = self.client.post("/runs/svc-diagnosis/diagnoses", json=payload)
        second = self.client.post(
            "/runs/svc-diagnosis/diagnoses",
            json={**payload, "classification": "AMBIGUOUS"},
        )

        self.assertEqual(200, first.status_code)
        self.assertEqual(1, first.json()["attempt"])
        self.assertEqual(
            "responses/failure-diagnosis/attempt-001/diagnosis.json",
            first.json()["artifact"],
        )
        self.assertEqual("gpt-5", first.json()["model"])
        self.assertEqual(2, second.json()["attempt"])

        artifact = (
            Path(self._tmp.name)
            / "svc-diagnosis"
            / "responses"
            / "failure-diagnosis"
            / "attempt-001"
            / "diagnosis.json"
        )
        self.assertTrue(artifact.is_file())
        self.assertEqual("openai", read_json(artifact)["provider"])

    def test_diagnosis_rejects_unknown_run_and_invalid_classification(self) -> None:
        valid_payload = {
            "schema_version": "1.0",
            "classification": "AMBIGUOUS",
            "rationale": "Invalid.",
            "provider": "openai",
            "model": "gpt-5",
            "created_at": "2026-07-29T12:00:00Z",
        }
        self.assertEqual(
            404,
            self.client.post("/runs/nope/diagnoses", json=valid_payload).status_code,
        )
        self.client.post("/runs", json=run_payload(run_id="svc-invalid-diagnosis", task="Tree2Graph"))
        self.assertEqual(
            422,
            self.client.post(
                "/runs/svc-invalid-diagnosis/diagnoses",
                json={**valid_payload, "classification": "NOT_A_CLASSIFICATION"},
            ).status_code,
        )


if __name__ == "__main__":
    unittest.main()
