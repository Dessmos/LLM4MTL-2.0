"""Recording a stage attempt: what is persisted, and how the service uses it.

These tests pin the recording owner's own contract, what the HTTP stage service
persists for one stage outcome, and two deliberate details: a stage is
announced before its work, and caller-supplied artifact references reach the
persisted result.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl import run_store
from llm4mtl.paths import ArtifactRoots
from llm4mtl.stages.models import StageResult
from llm4mtl.provenance import build_provenance
from llm4mtl.serialization.json_io import read_json
from llm4mtl.stage_recording import (
    announce_stage_start,
    infrastructure_error_result,
    record_stage_attempt,
)
from llm4mtl.stage_service.app import app
from run_records import read_events

IDENTITY = {
    "language": "etl",
    "task": "Tree2Graph",
    "transformation_model": "gpt-5",
    "test_generation_model": "gpt-5",
    "transformation_strategy": "grammar",
    "test_generation_strategy": "few_shot",
    "seed": 1,
    "pipeline_variant": "full",
    "provenance": build_provenance("etl", "Tree2Graph"),
}

# One extraction outcome, recorded through the service below.
EXTRACTION_COUNTS = {"selected": 2, "created": 2, "failed": 0}
EXTRACTION_DETAILS = {"results_file": "artifacts/work/extraction.csv"}


def extraction_result() -> StageResult:
    """A fresh result per call, so no test sees another's mutation."""
    return StageResult(
        "extraction",
        "completed",
        dict(EXTRACTION_COUNTS),
        dict(EXTRACTION_DETAILS),
    )


def stage_events(paths: run_store.RunPaths) -> list[dict[str, object]]:
    """Stage-scoped events without their wall-clock timestamps."""
    return [
        {
            key: value
            for key, value in event.items()
            if key not in {"ts", "schema_version"}
        }
        for event in read_events(paths)
        if str(event["event"]).startswith("stage_")
    ]


class SharedOwnerContractTests(unittest.TestCase):
    """What record_stage_attempt guarantees to whoever calls it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.paths = run_store.create_run(Path(self._tmp.name), "run-owner", IDENTITY)

    def test_returned_payload_is_the_payload_that_was_persisted(self) -> None:
        recorded = record_stage_attempt(self.paths, "extract", extraction_result())

        persisted = read_json(
            self.paths.stage_attempt_result("extract", recorded.attempt)
        )
        self.assertEqual(persisted, recorded.payload)
        # The attempt number is part of the contract a caller may hand to n8n,
        # so it must not be something only the persisted copy knows.
        self.assertEqual(1, recorded.payload["attempt"])

    def test_internal_evidence_is_stored_beside_the_contract_result(self) -> None:
        recorded = record_stage_attempt(self.paths, "extract", extraction_result())

        evidence = read_json(
            self.paths.stage_attempt_evidence("extract", recorded.attempt)
        )
        self.assertEqual(EXTRACTION_COUNTS, evidence["counts"])
        self.assertEqual(EXTRACTION_DETAILS, evidence["details"])
        # Evidence is not the n8n contract and must not be confused with it.
        self.assertNotIn("outcome_code", evidence)

    def test_finished_event_carries_the_recorded_attempt(self) -> None:
        recorded = record_stage_attempt(self.paths, "extract", extraction_result())

        self.assertEqual(
            [
                {
                    "event": "stage_finished",
                    "stage": "extract",
                    "status": "passed",
                    "outcome_code": "EXTRACTED",
                    "attempt": recorded.attempt,
                }
            ],
            stage_events(self.paths),
        )

    def test_caller_supplied_artifacts_join_the_persisted_result(self) -> None:
        recorded = record_stage_attempt(
            self.paths,
            "extract",
            extraction_result(),
            artifacts={
                "semantic_test_generation_record": "generations/semantic-test.json"
            },
        )

        persisted = read_json(
            self.paths.stage_attempt_result("extract", recorded.attempt)
        )
        self.assertEqual(
            {
                "results_file": "artifacts/work/extraction.csv",
                "semantic_test_generation_record": "generations/semantic-test.json",
            },
            persisted["artifacts"],
        )

    def test_a_non_execution_stage_prepares_no_diagnosis(self) -> None:
        recorded = record_stage_attempt(self.paths, "extract", extraction_result())
        self.assertIsNone(recorded.diagnosis_index)

    def test_announcing_a_start_is_a_separate_step(self) -> None:
        """The two callers announce at different moments, so it is not folded in."""
        announce_stage_start(self.paths, "extract")
        self.assertEqual(
            [{"event": "stage_started", "stage": "extract"}],
            stage_events(self.paths),
        )


class InfrastructureErrorResultTests(unittest.TestCase):

    def test_a_raised_exception_becomes_an_observation_free_result(self) -> None:
        result = infrastructure_error_result(
            "extraction", RuntimeError("adapter failed")
        )

        self.assertEqual("infrastructure_error", result.status)
        self.assertEqual({"infrastructure_errors": 1}, result.counts)
        self.assertEqual("RuntimeError: adapter failed", result.details["error"])
        self.assertEqual(1, result.exit_code)
        self.assertEqual("", result.input_hash)


BATCH = "batch_001"


class ServiceRecordingTests(unittest.TestCase):
    """What the stage service persists for one extraction outcome."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.artifacts = ArtifactRoots(Path(self._tmp.name).resolve())
        self.batch = run_store.create_batch(self.artifacts.runs, {}, batch_id=BATCH)
        roots_patcher = patch(
            "llm4mtl.stage_service.app._artifact_roots", return_value=self.artifacts
        )
        roots_patcher.start()
        self.addCleanup(roots_patcher.stop)
        self.client = TestClient(app)

    def _record_through_service(self, run_id: str) -> run_store.RunPaths:
        self.client.post(
            f"/batches/{BATCH}/runs",
            json={
                "language": "etl",
                "task": "Tree2Graph",
                "transformation_model": "gpt-5",
                "test_generation_model": "gpt-5",
                "transformation_strategy": "grammar",
                "test_generation_strategy": "few_shot",
                "run_id": run_id,
            },
        )
        with patch(
            "llm4mtl.stage_service.app._stages.tests.extract",
            side_effect=lambda *_: extraction_result(),
        ):
            response = self.client.post(f"/batches/{BATCH}/runs/{run_id}/stages/extract", json={})
        self.assertEqual(200, response.status_code)
        return run_store.open_run(self.batch.root, run_id)

    def test_the_persisted_result_is_the_contract_payload(self) -> None:
        paths = self._record_through_service("result")

        persisted = read_json(paths.stage_attempt_result("extract", 1))

        self.assertEqual("extract", persisted["stage"])
        self.assertEqual("passed", persisted["status"])
        self.assertEqual("EXTRACTED", persisted["outcome_code"])
        self.assertEqual(EXTRACTION_COUNTS, persisted["counts"])
        self.assertEqual(1, persisted["attempt"])

    def test_the_stage_is_announced_before_it_finishes(self) -> None:
        paths = self._record_through_service("events")

        self.assertEqual(
            [
                {"event": "stage_started", "stage": "extract"},
                {
                    "event": "stage_finished",
                    "stage": "extract",
                    "status": "passed",
                    "outcome_code": "EXTRACTED",
                    "attempt": 1,
                },
            ],
            stage_events(paths),
        )

    def test_the_internal_evidence_is_the_stage_result(self) -> None:
        paths = self._record_through_service("evidence")

        evidence = read_json(paths.stage_attempt_evidence("extract", 1))

        self.assertEqual("completed", evidence["status"])
        self.assertEqual(EXTRACTION_COUNTS, evidence["counts"])
        self.assertEqual(EXTRACTION_DETAILS, evidence["details"])


if __name__ == "__main__":
    unittest.main()
