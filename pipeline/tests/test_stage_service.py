from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl.stage_service.app import app


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
        created = self.client.post("/runs", json={"run_id": "svc-1", "language": "etl", "task": "Tree2Graph"})
        self.assertEqual(200, created.status_code)
        self.assertEqual({"run_id": "svc-1", "status": "initialized"}, created.json())

        fetched = self.client.get("/runs/svc-1")
        self.assertEqual(200, fetched.status_code)
        self.assertEqual("etl", fetched.json()["manifest"]["language"])
        self.assertEqual("svc-1", fetched.json()["manifest"]["run_id"])

    def test_create_run_refuses_to_replace_existing_manifest(self) -> None:
        first = self.client.post(
            "/runs", json={"run_id": "svc-immutable", "task": "Tree2Graph"}
        )
        duplicate = self.client.post(
            "/runs", json={"run_id": "svc-immutable", "task": "OO2DB"}
        )
        self.assertEqual(200, first.status_code)
        self.assertEqual(409, duplicate.status_code)
        fetched = self.client.get("/runs/svc-immutable")
        self.assertEqual("Tree2Graph", fetched.json()["manifest"]["task"])

    def test_unknown_run_and_unknown_stage_return_404(self) -> None:
        self.assertEqual(404, self.client.post("/runs/nope/stages/extract", json={}).status_code)
        self.client.post("/runs", json={"run_id": "svc-2"})
        self.assertEqual(404, self.client.post("/runs/svc-2/stages/not-a-stage", json={}).status_code)

    def test_stage_returns_and_records_outcome_code(self) -> None:
        self.client.post("/runs", json={"run_id": "svc-3"})
        response = self.client.post("/runs/svc-3/stages/extract", json={"tasks": ["NoSuchTask"]})
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual("extract", body["stage"])
        self.assertEqual("infrastructure_error", body["status"])
        self.assertEqual("INFRASTRUCTURE_ERROR", body["outcome_code"])
        self.assertEqual(1, body["attempt"])

        # The result is persisted and readable via GET (n8n's latest.json projection).
        fetched = self.client.get("/runs/svc-3/stages/extract")
        self.assertEqual(200, fetched.status_code)
        self.assertEqual("INFRASTRUCTURE_ERROR", fetched.json()["outcome_code"])

    def test_stage_exception_is_recorded_as_infrastructure_error(self) -> None:
        self.client.post("/runs", json={"run_id": "svc-4"})
        with patch(
            "llm4mtl.stage_service.app._orchestrator.tests.extract",
            side_effect=RuntimeError("adapter failed"),
        ):
            response = self.client.post(
                "/runs/svc-4/stages/extract", json={"tasks": ["Tree2Graph"]}
            )
        self.assertEqual(200, response.status_code)
        self.assertEqual("infrastructure_error", response.json()["status"])
        self.assertEqual("INFRASTRUCTURE_ERROR", response.json()["outcome_code"])
        self.assertEqual(1, response.json()["attempt"])


if __name__ == "__main__":
    unittest.main()
