"""Integrity invariants of the run store: containment, atomicity, schema conformance."""

from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from llm4mtl import experiment_store, run_store
from llm4mtl.artifact_schemas import ArtifactSchemaError, validate_artifact
from llm4mtl.run_store.identity import InvalidRunIdError
from llm4mtl.stage_contract import SCHEMA_VERSION as STAGE_SCHEMA_VERSION

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


def stage_result(outcome_code: str) -> dict[str, object]:
    return {
        "schema_version": STAGE_SCHEMA_VERSION,
        "status": "passed",
        "outcome_code": outcome_code,
    }


class RunIdContainmentTests(unittest.TestCase):

    def test_ids_that_escape_the_runs_root_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir) / "runs"
            runs_root.mkdir()
            for run_id in (
                "../escape",
                "..",
                ".",
                "nested/run",
                "/absolute",
                "",
                "run id",
            ):
                with self.subTest(run_id=run_id):
                    with self.assertRaises(InvalidRunIdError):
                        run_store.open_run(runs_root, run_id)

    def test_creating_a_run_with_a_traversing_id_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir) / "runs"
            runs_root.mkdir()
            with self.assertRaises(InvalidRunIdError):
                run_store.create_run(runs_root, "../outside", IDENTITY)
            self.assertEqual([], list(Path(temp_dir).glob("outside")))

    def test_ordinary_generated_ids_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_root = Path(temp_dir) / "runs"
            runs_root.mkdir()
            for run_id in (
                "etl-tree2graph-20260729-120000-000001",
                "exp__etl__seed1",
                "run.1",
            ):
                with self.subTest(run_id=run_id):
                    self.assertEqual(
                        runs_root.resolve() / run_id,
                        run_store.open_run(runs_root, run_id).root,
                    )

    def test_experiment_ids_are_contained_too(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(InvalidRunIdError):
                experiment_store.open_experiment(Path(temp_dir), "../escape")


class AttemptAtomicityTests(unittest.TestCase):

    def test_concurrent_run_creation_has_exactly_one_manifest_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            def create(index: int) -> str:
                try:
                    run_store.create_run(
                        root,
                        "same-run",
                        {**IDENTITY, "seed": index},
                    )
                except run_store.ManifestExistsError:
                    return "lost"
                return "won"

            with ThreadPoolExecutor(max_workers=8) as pool:
                outcomes = list(pool.map(create, range(8)))

            self.assertEqual(1, outcomes.count("won"))
            validate_artifact(
                "manifest",
                run_store.read_manifest(run_store.open_run(root, "same-run")),
            )

    def test_concurrent_attempts_never_share_a_number(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            recorded = 12

            with ThreadPoolExecutor(max_workers=8) as pool:
                attempts = list(
                    pool.map(
                        lambda index: run_store.record_attempt(
                            paths, "execution", stage_result(f"OUTCOME_{index}")
                        ),
                        range(recorded),
                    )
                )

            self.assertEqual(recorded, len(set(attempts)))
            self.assertEqual(set(range(1, recorded + 1)), set(attempts))
            for attempt in attempts:
                self.assertTrue(
                    paths.stage_attempt_result("execution", attempt).is_file()
                )

    def test_concurrent_diagnoses_never_share_a_number(self) -> None:
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

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(
                    pool.map(
                        lambda _: run_store.record_diagnosis(
                            paths, diagnosis, Path(temp_dir) / "diagnoses"
                        ),
                        range(8),
                    )
                )

            self.assertEqual(8, len({attempt for attempt, _ in results}))


class PersistedSchemaTests(unittest.TestCase):

    def test_manifest_without_identity_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ArtifactSchemaError):
                run_store.create_run(
                    Path(temp_dir), "run_001", {"language": "etl", "task": "T"}
                )

    def test_manifest_with_unknown_language_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ArtifactSchemaError):
                run_store.create_run(
                    Path(temp_dir), "run_001", {**IDENTITY, "language": "cobol"}
                )

    def test_stage_result_outside_the_contract_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            with self.assertRaises(ArtifactSchemaError):
                run_store.record_attempt(paths, "execution", {"status": "passed"})
            with self.assertRaises(ArtifactSchemaError):
                run_store.record_attempt(
                    paths,
                    "execution",
                    {
                        "schema_version": STAGE_SCHEMA_VERSION,
                        "status": "completed",
                        "outcome_code": "X",
                    },
                )
            self.assertFalse(paths.stage_attempts_dir("execution").exists())

    def test_event_outside_the_contract_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            with self.assertRaises(ArtifactSchemaError):
                run_store.append_event(paths, "not_an_event")

    def test_schema_formats_are_enforced_not_only_documented(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            with self.assertRaises(ArtifactSchemaError):
                run_store.record_diagnosis(
                    paths,
                    {
                        "schema_version": "1.0",
                        "classification": "AMBIGUOUS",
                        "rationale": "Evidence is inconclusive.",
                        "provider": "openai",
                        "model": "gpt-5",
                        "created_at": "not-a-date",
                    },
                    Path(temp_dir) / "diagnoses",
                )

    def test_every_persisted_artifact_of_a_run_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = run_store.create_run(Path(temp_dir), "run_001", IDENTITY)
            run_store.record_attempt(paths, "extract", stage_result("EXTRACTED"))

            validate_artifact("manifest", run_store.read_manifest(paths))
            for event in run_store.read_events(paths):
                validate_artifact("events", event)
            validate_artifact("stage-result", run_store.read_latest(paths, "extract"))


if __name__ == "__main__":
    unittest.main()
