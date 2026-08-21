"""A run judges its own copy of the transformation, not the shared latest one.

Generation writes one file per (language, model, strategy, task). The next run
over the same combination overwrites it, so a finished run that cites that path
cites bytes that may already be gone — and the two stages that judge a
transformation can even end up judging different files within one run. These
tests pin that the run adopts the file once and that every later stage reads the
adopted copy.
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
from llm4mtl.provenance import build_provenance
from llm4mtl.run_store.transformations import (
    TransformationAdoptionError,
    adopt_transformations,
    adopted_transformations,
    iteration_from_suite_id,
    transformation_dir,
)
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
GENERATED = "rule Tree2Node transform t : Source!Tree to n : Target!Node {}\n"
REGENERATED = "rule Tree2Node transform t : Tree!Tree to n : Graph!Node {}\n"


class SuiteIterationTests(unittest.TestCase):
    def test_the_iteration_is_read_from_the_suite_id_the_master_already_carries(
        self,
    ) -> None:
        self.assertEqual(0, iteration_from_suite_id("run-1_000"))
        self.assertEqual(2, iteration_from_suite_id("run-1_002"))
        # No suite id, or one that encodes no iteration, is the initial one:
        # inventing a number would attribute a refinement that never happened.
        self.assertEqual(0, iteration_from_suite_id(None))
        self.assertEqual(0, iteration_from_suite_id("run-1"))


class TransformationAdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.paths = run_store.create_run(
            self.root / "runs",
            "adopt-1",
            {
                **IDENTITY,
                "seed": 1,
                "pipeline_variant": "full",
                "provenance": build_provenance(IDENTITY["language"], IDENTITY["task"]),
            },
        )
        self.manifest = run_store.read_manifest(self.paths)
        self.shared = self.root / "shared" / "Tree2Graph.etl"
        self.shared.parent.mkdir(parents=True)
        self.shared.write_text(GENERATED, encoding="utf-8")

    def test_adoption_copies_the_file_and_records_where_it_came_from(self) -> None:
        adopted = adopt_transformations(self.paths, self.manifest, [self.shared])

        self.assertIsNotNone(adopted)
        copy = adopted.paths[0]
        self.assertEqual(GENERATED, copy.read_text(encoding="utf-8"))
        # The task name is kept: the execution stage pairs a suite with a
        # transformation by that stem.
        self.assertEqual("Tree2Graph.etl", copy.name)
        self.assertEqual(
            transformation_dir(self.paths, 0) / "Tree2Graph.etl", copy
        )

        metadata = read_json(adopted.metadata)
        self.assertEqual("1.0", metadata["schema_version"])
        self.assertEqual("Tree2Graph", metadata["task"])
        self.assertEqual("gpt-5", metadata["model"])
        self.assertEqual("few_shots_AND_grammar", metadata["strategy"])
        entry = metadata["transformations"][0]
        self.assertEqual("transformation/iteration-000/Tree2Graph.etl", entry["path"])
        self.assertEqual(len(GENERATED.encode("utf-8")), entry["bytes"])
        self.assertTrue(entry["source"].endswith("Tree2Graph.etl"))
        self.assertEqual(64, len(entry["sha256"]))

    def test_a_later_generation_cannot_change_what_the_run_already_adopted(
        self,
    ) -> None:
        adopted = adopt_transformations(self.paths, self.manifest, [self.shared])
        # The next run over the same combination overwrites the shared file
        # while this run is still executing.
        self.shared.write_text(REGENERATED, encoding="utf-8")

        recovered = adopted_transformations(self.paths, 0)

        self.assertEqual(adopted.paths, recovered.paths)
        self.assertEqual(GENERATED, recovered.paths[0].read_text(encoding="utf-8"))
        # Re-adopting the changed bytes under the same iteration is the loss this
        # module exists to prevent, so it is refused rather than recorded.
        with self.assertRaises(TransformationAdoptionError):
            adopt_transformations(self.paths, self.manifest, [self.shared])

    def test_a_modified_adopted_file_is_rejected_on_read(self) -> None:
        adopted = adopt_transformations(self.paths, self.manifest, [self.shared])
        adopted.paths[0].write_text(REGENERATED, encoding="utf-8")

        with self.assertRaisesRegex(
            TransformationAdoptionError, "changed after adoption"
        ):
            adopted_transformations(self.paths, 0)

    def test_adopted_metadata_cannot_escape_the_run(self) -> None:
        adopted = adopt_transformations(self.paths, self.manifest, [self.shared])
        outside = self.root / "outside.etl"
        outside.write_text(GENERATED, encoding="utf-8")
        metadata = read_json(adopted.metadata)
        metadata["transformations"][0]["path"] = "../../outside.etl"
        write_json(adopted.metadata, metadata)

        with self.assertRaisesRegex(TransformationAdoptionError, "escapes the run"):
            adopted_transformations(self.paths, 0)

    def test_each_refinement_iteration_keeps_its_own_transformation(self) -> None:
        adopt_transformations(self.paths, self.manifest, [self.shared])
        self.shared.write_text(REGENERATED, encoding="utf-8")

        refined = adopt_transformations(
            self.paths, self.manifest, [self.shared], iteration=1
        )

        self.assertEqual(REGENERATED, refined.paths[0].read_text(encoding="utf-8"))
        # Comparing an initial transformation with its refinement is the point of
        # the refinement loop, so both have to survive.
        initial = adopted_transformations(self.paths, 0)
        self.assertEqual(GENERATED, initial.paths[0].read_text(encoding="utf-8"))
        self.assertNotEqual(refined.directory, initial.directory)

    def test_nothing_to_adopt_stays_nothing(self) -> None:
        """A run with no generated transformation adopts none and says so.

        Turning that into an adoption error would replace the stage's own
        "selected 0 transformations" with an infrastructure failure.
        """
        self.assertIsNone(adopt_transformations(self.paths, self.manifest, []))
        self.assertIsNone(adopted_transformations(self.paths, 0))


class StageServiceAdoptionTests(unittest.TestCase):
    """What the stages actually receive once the service adopts."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self._diagnoses = self.root / "diagnoses"
        self.addCleanup(lambda: shutil.rmtree(self._diagnoses, ignore_errors=True))
        for target, value in (
            ("_runs_root", self.root / "runs"),
            ("_diagnoses_root", self._diagnoses),
        ):
            patcher = patch(
                f"llm4mtl.stage_service.app.{target}", return_value=value
            )
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)
        self.client.post("/runs", json={**IDENTITY, "run_id": "svc-adopt"})
        self.shared = (
            self.root
            / "runs"
            / "svc-adopt"
            / "responses"
            / "transformation-generation"
            / "iteration-000"
            / "Tree2Graph.etl"
        )
        self.shared.parent.mkdir(parents=True)
        self.shared.write_text(GENERATED, encoding="utf-8")

    def _run_stage(
        self,
        stage: str,
        adapter: str,
        method: str,
        body: dict[str, object] | None = None,
    ) -> PipelineConfig:
        """Run one stage and return the config its adapter was handed."""
        seen: list[PipelineConfig] = []

        def capture(config: PipelineConfig, dry_run: bool) -> StageResult:
            seen.append(config)
            return StageResult("transformation_parsing", "passed", {"selected": 1}, {})

        with (
            patch(
                "llm4mtl.stage_service.app._orchestrator.prepare_workspace",
                return_value=self.root / "workspace",
            ),
            patch(
                f"llm4mtl.stage_service.app._orchestrator.{adapter}.{method}",
                side_effect=capture,
            ),
        ):
            response = self.client.post(
                f"/runs/svc-adopt/stages/{stage}",
                json=body if body is not None else {"suite_id": "svc-adopt_000"},
            )
        self.assertEqual(200, response.status_code, response.text)
        return seen[0]

    def test_both_transformation_stages_judge_the_run_s_own_copy(self) -> None:
        syntax = self._run_stage("syntax-validation", "parser", "parse")
        run_dir = (self.root / "runs" / "svc-adopt").resolve()
        adopted = run_dir / "transformation" / "iteration-000" / "Tree2Graph.etl"
        self.assertEqual([str(adopted)], syntax.transformations)

        # The shared file changes between the two stages, exactly as a parallel
        # run over the same combination would change it.
        self.shared.write_text(REGENERATED, encoding="utf-8")
        execution = self._run_stage("execution", "transformations", "semantic_validation")

        self.assertEqual([str(adopted)], execution.transformations)
        self.assertEqual(GENERATED, adopted.read_text(encoding="utf-8"))


    def test_a_refined_transformation_is_adopted_under_its_own_iteration(self) -> None:
        """The iteration is stated, not inferred from the suite id.

        A refined *transformation* is judged against the suite that was already
        validated, so the suite id stays at iteration 000 while the
        transformation moves on. Reading the iteration off the suite id would
        make the refined transformation look like the initial one and refuse to
        adopt it.
        """
        self._run_stage("syntax-validation", "parser", "parse")
        refined_response = (
            self.root
            / "runs"
            / "svc-adopt"
            / "responses"
            / "transformation-generation"
            / "iteration-001"
            / "Tree2Graph.etl"
        )
        refined_response.parent.mkdir(parents=True)
        refined_response.write_text(REGENERATED, encoding="utf-8")

        refined = self._run_stage(
            "syntax-validation",
            "parser",
            "parse",
            body={"suite_id": "svc-adopt_000", "refinement_iteration": 1},
        )

        run_dir = (self.root / "runs" / "svc-adopt").resolve()
        self.assertEqual(
            [str(run_dir / "transformation" / "iteration-001" / "Tree2Graph.etl")],
            refined.transformations,
        )
        initial = run_dir / "transformation" / "iteration-000" / "Tree2Graph.etl"
        self.assertEqual(GENERATED, initial.read_text(encoding="utf-8"))
        self.assertEqual(
            REGENERATED, Path(refined.transformations[0]).read_text(encoding="utf-8")
        )

    def test_master_iteration_cannot_fall_back_to_a_shared_transformation(self) -> None:
        self.shared.unlink()

        response = self.client.post(
            "/runs/svc-adopt/stages/syntax-validation",
            json={"suite_id": "svc-adopt_000", "refinement_iteration": 0},
        )

        self.assertEqual(409, response.status_code, response.text)
        self.assertIn("run-scoped generated transformation is missing", response.text)


if __name__ == "__main__":
    unittest.main()
