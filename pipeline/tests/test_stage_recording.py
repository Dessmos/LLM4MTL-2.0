"""Recording a stage attempt is one policy, and both entry points obey it.

A run directory is read without knowing whether the local runner or the HTTP
stage service produced it, so what an attempt records must not depend on which
one ran. These tests pin that: the shared owner's own contract, the equivalence
of the two callers over the same stage outcome, and the two differences that
are deliberate — when a stage is announced, and which artifact references reach
the persisted result rather than only the service's response.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl import run_store
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.provenance import build_provenance
from llm4mtl.serialization.json_io import read_json
from llm4mtl.stage_recording import (
    announce_stage_start,
    infrastructure_error_result,
    record_stage_attempt,
)
from llm4mtl.stage_service.app import app

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

# One extraction outcome, recorded through both entry points below.
EXTRACTION_COUNTS = {"selected": 2, "created": 2, "failed": 0}
EXTRACTION_DETAILS = {"results_file": "artifacts/work/extraction.csv"}


def extraction_result() -> StageResult:
    """A fresh result per call: the runner plans and then runs the stage."""
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
        for event in run_store.read_events(paths)
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

    def test_the_planned_input_hash_is_kept_when_the_caller_knows_it(self) -> None:
        result = infrastructure_error_result(
            "extraction",
            OSError("disk full"),
            input_hash="abc123",
        )
        self.assertEqual("abc123", result.input_hash)


class CallerEquivalenceTests(unittest.TestCase):
    """The same stage outcome records the same way through either entry point."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        # Resolved: the run store resolves a run directory, and the runner
        # reports it relative to the repository root patched in below.
        self.runs_root = Path(self._tmp.name).resolve()
        self._diagnoses = self.runs_root.parent / f"{self.runs_root.name}-diagnoses"
        self.addCleanup(lambda: shutil.rmtree(self._diagnoses, ignore_errors=True))
        runs_patcher = patch(
            "llm4mtl.stage_service.app._runs_root", return_value=self.runs_root
        )
        runs_patcher.start()
        self.addCleanup(runs_patcher.stop)
        diagnoses_patcher = patch(
            "llm4mtl.stage_service.app._diagnoses_root", return_value=self._diagnoses
        )
        diagnoses_patcher.start()
        self.addCleanup(diagnoses_patcher.stop)
        self.client = TestClient(app)

    def _extraction_config(self, run_id: str) -> PipelineConfig:
        return PipelineConfig(
            language="etl",
            tasks=["Tree2Graph"],
            test_models=["gpt-5"],
            test_strategies=["few_shot"],
            transformation_models=["gpt-5"],
            transformation_strategies=["grammar"],
            run_id=run_id,
            command="tests.extract",
        )

    def _run_locally(self, config: PipelineConfig, extract):
        """Drive the local runner with its runs root inside a temporary tree."""
        orchestrator = ExperimentOrchestrator()
        orchestrator.runs_root = self.runs_root
        with (
            # The runner reports its run directory relative to the repository
            # root; the fixture's runs live outside it.
            patch("llm4mtl.experiment_runner.orchestrator.REPO_ROOT", self.runs_root),
            patch.object(orchestrator.tests, "extract", side_effect=extract),
        ):
            return orchestrator.run(config)

    def _record_through_runner(self, run_id: str) -> run_store.RunPaths:
        self._run_locally(
            self._extraction_config(run_id),
            lambda *_: extraction_result(),
        )
        return run_store.open_run(self.runs_root, run_id)

    def _record_through_service(self, run_id: str) -> run_store.RunPaths:
        self.client.post(
            "/runs",
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
            "llm4mtl.stage_service.app._orchestrator.tests.extract",
            side_effect=lambda *_: extraction_result(),
        ):
            response = self.client.post(f"/runs/{run_id}/stages/extract", json={})
        self.assertEqual(200, response.status_code)
        return run_store.open_run(self.runs_root, run_id)

    def test_both_entry_points_persist_the_same_stage_result(self) -> None:
        runner = self._record_through_runner("equiv-runner")
        service = self._record_through_service("equiv-service")

        self.assertEqual(
            read_json(runner.stage_attempt_result("extract", 1)),
            read_json(service.stage_attempt_result("extract", 1)),
        )

    def test_both_entry_points_record_the_same_stage_events(self) -> None:
        runner = self._record_through_runner("events-runner")
        service = self._record_through_service("events-service")

        expected = [
            {"event": "stage_started", "stage": "extract"},
            {
                "event": "stage_finished",
                "stage": "extract",
                "status": "passed",
                "outcome_code": "EXTRACTED",
                "attempt": 1,
            },
        ]
        self.assertEqual(expected, stage_events(runner))
        self.assertEqual(expected, stage_events(service))

    def test_both_entry_points_store_the_same_internal_evidence(self) -> None:
        runner = self._record_through_runner("evidence-runner")
        service = self._record_through_service("evidence-service")

        runner_evidence = read_json(runner.stage_attempt_evidence("extract", 1))
        service_evidence = read_json(service.stage_attempt_evidence("extract", 1))
        for field in ("counts", "details", "status"):
            self.assertEqual(runner_evidence[field], service_evidence[field])

    def test_the_runner_records_a_raised_stage_as_an_infrastructure_error(self) -> None:
        """The runner's exception path, like the service's, still records an attempt."""

        def plan_then_raise(_config: PipelineConfig, dry_run: bool) -> StageResult:
            if dry_run:
                planned = extraction_result()
                planned.input_hash = "planned-input-hash"
                return planned
            raise RuntimeError("adapter failed")

        result = self._run_locally(
            self._extraction_config("runner-raises"),
            plan_then_raise,
        )

        self.assertEqual("failed", result.status)
        paths = run_store.open_run(self.runs_root, "runner-raises")
        persisted = read_json(paths.stage_attempt_result("extract", 1))
        self.assertEqual("infrastructure_error", persisted["status"])
        self.assertEqual("INFRASTRUCTURE_ERROR", persisted["outcome_code"])
        evidence = read_json(paths.stage_attempt_evidence("extract", 1))
        self.assertEqual("RuntimeError: adapter failed", evidence["details"]["error"])
        # The plan's input hash survives the failure, so a resume can still tell
        # whether the inputs changed since the attempt that failed.
        self.assertEqual("planned-input-hash", evidence["input_hash"])


if __name__ == "__main__":
    unittest.main()
