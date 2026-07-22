from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm4mtl import run_store
from llm4mtl.run_store import ManifestExistsError
from llm4mtl.serialization.json_io import read_json


class ManifestTests(unittest.TestCase):
    def test_manifest_is_write_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(
                Path(temp_dir), "run_001", {"language": "etl", "task": "Tree2Graph"}
            )
            manifest = run_store.read_manifest(paths)
            self.assertEqual("run_001", manifest["run_id"])
            self.assertEqual("1.0", manifest["schema_version"])
            self.assertIn("started_at", manifest)
            with self.assertRaises(ManifestExistsError):
                run_store.write_manifest(paths, {"run_id": "run_001"})


class StageAttemptTests(unittest.TestCase):
    def test_attempts_are_immutable_and_latest_tracks_newest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", {})
            first = run_store.record_attempt(
                paths, "syntax-validation", {"status": "failed", "outcome_code": "SYNTAX_INVALID"}
            )
            second = run_store.record_attempt(
                paths, "syntax-validation", {"status": "passed", "outcome_code": "SYNTAX_VALID"}
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


class EventLogTests(unittest.TestCase):
    def test_events_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", {})
            run_store.append_event(paths, "stage_started", stage="extraction")
            run_store.append_event(
                paths, "stage_finished", stage="extraction", status="passed", outcome_code="EXTRACTED"
            )
            events = run_store.read_events(paths)
            self.assertEqual(3, len(events))
            self.assertEqual("run_created", events[0]["event"])
            self.assertEqual("EXTRACTED", events[-1]["outcome_code"])


if __name__ == "__main__":
    unittest.main()
