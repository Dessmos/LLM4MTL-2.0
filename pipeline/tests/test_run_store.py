from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm4mtl import run_store
from llm4mtl.stage_contract import SCHEMA_VERSION as STAGE_SCHEMA_VERSION
from llm4mtl.run_store import ManifestExistsError
from llm4mtl.serialization.json_io import read_json

from llm4mtl.provenance import build_provenance

# A run is exactly one combination, so the fixture states every identity axis.
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


def stage_result(outcome_code: str, status: str = "passed") -> dict[str, object]:
    """A minimal payload conforming to schemas/stage-result.schema.json."""
    return {"schema_version": STAGE_SCHEMA_VERSION, "status": status, "outcome_code": outcome_code}


class ManifestTests(unittest.TestCase):
    def test_manifest_is_write_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            manifest = run_store.read_manifest(paths)
            self.assertEqual("run_001", manifest["run_id"])
            self.assertEqual(run_store.SCHEMA_VERSION, manifest["schema_version"])
            self.assertIn("started_at", manifest)
            with self.assertRaises(ManifestExistsError):
                run_store.write_manifest(paths, {"run_id": "run_001", **IDENTITY})


class StageAttemptTests(unittest.TestCase):
    def test_attempts_are_immutable_and_latest_tracks_newest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            first = run_store.record_attempt(
                paths, "syntax-validation", stage_result("SYNTAX_INVALID", "failed")
            )
            second = run_store.record_attempt(
                paths, "syntax-validation", stage_result("SYNTAX_VALID")
            )
            self.assertEqual((1, 2), (first, second))

            # A repeated stage does NOT overwrite attempt-001.
            attempt_one = paths.stage_attempt_result("syntax-validation", 1)
            attempt_two = paths.stage_attempt_result("syntax-validation", 2)
            self.assertTrue(attempt_one.is_file())
            self.assertTrue(attempt_two.is_file())
            self.assertEqual("SYNTAX_INVALID", read_json(attempt_one)["outcome_code"])

            latest = run_store.read_latest(paths, "syntax-validation")
            self.assertEqual("SYNTAX_VALID", latest["outcome_code"])
            self.assertEqual(2, latest["attempt"])

    def test_internal_evidence_is_stored_beside_the_contract_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            attempt = run_store.record_attempt(
                paths,
                "extract",
                stage_result("EXTRACTED"),
                evidence={"command": ["python", "extract.py"], "stdout": "Extracted: 1; failed: 0"},
            )

            result = read_json(paths.stage_attempt_result("extract", attempt))
            evidence = read_json(paths.stage_attempt_evidence("extract", attempt))
            self.assertNotIn("stdout", result)
            self.assertEqual("Extracted: 1; failed: 0", evidence["stdout"])


class ResponseAttemptTests(unittest.TestCase):
    def test_diagnoses_are_stored_as_immutable_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            diagnosis = {
                "schema_version": "1.0",
                "classification": "AMBIGUOUS",
                "rationale": "Evidence is inconclusive.",
                "provider": "openai",
                "model": "gpt-5",
                "created_at": "2026-07-29T12:00:00Z",
            }

            # A diagnosis is a result other work consumes, so it is stored
            # outside the run's own state and keyed by the run that produced it.
            diagnoses_root = Path(temp_dir) / "diagnoses"
            first, first_artifact = run_store.record_diagnosis(
                paths, diagnosis, diagnoses_root
            )
            second, second_artifact = run_store.record_diagnosis(
                paths, {**diagnosis, "classification": "TEST_DEFECT"}, diagnoses_root
            )

            self.assertEqual((1, 2), (first, second))
            self.assertEqual("run_001/attempt-001/diagnosis.json", first_artifact)
            self.assertEqual("run_001/attempt-002/diagnosis.json", second_artifact)
            self.assertEqual(
                "AMBIGUOUS",
                read_json(diagnoses_root / first_artifact)["classification"],
            )
            # Nothing about the diagnosis is left behind in the run.
            self.assertFalse((paths.responses_dir / "failure-diagnosis").exists())


class EventLogTests(unittest.TestCase):
    def test_events_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            run_store.append_event(paths, "stage_started", stage="extract")
            run_store.append_event(
                paths, "stage_finished", stage="extract", status="passed", outcome_code="EXTRACTED"
            )
            events = run_store.read_events(paths)
            self.assertEqual(3, len(events))
            self.assertEqual("run_created", events[0]["event"])
            self.assertEqual("EXTRACTED", events[-1]["outcome_code"])

    def test_concurrent_event_appends_remain_complete_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            count = 40
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(
                    pool.map(
                        lambda _: run_store.append_event(
                            paths,
                            "stage_started",
                            stage="extract",
                        ),
                        range(count),
                    )
                )

            events = run_store.read_events(paths)
            self.assertEqual(count + 1, len(events))


if __name__ == "__main__":
    unittest.main()
