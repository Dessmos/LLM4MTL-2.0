from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from llm4mtl.experiment_runner.models import StageResult
from llm4mtl import run_store
from llm4mtl.provenance import build_provenance
from llm4mtl.serialization.json_io import read_json, write_json
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
        self._diagnoses = Path(self._tmp.name).parent / f"{Path(self._tmp.name).name}-diagnoses"
        patcher = patch(
            "llm4mtl.stage_service.app._runs_root", return_value=Path(self._tmp.name)
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        diagnoses_patcher = patch(
            "llm4mtl.stage_service.app._diagnoses_root", return_value=self._diagnoses
        )
        diagnoses_patcher.start()
        self.addCleanup(diagnoses_patcher.stop)
        self.addCleanup(lambda: shutil.rmtree(self._diagnoses, ignore_errors=True))
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

    def test_openapi_documents_explicit_http_errors(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]
        expected = {
            ("/prompt-inputs/resolve", "post"): {"422"},
            ("/runs", "post"): {"400", "409", "422"},
            ("/runs/{run_id}/stages/{stage}", "post"): {"400", "404", "409"},
            ("/runs/{run_id}/stages/{stage}", "get"): {"400", "404"},
            ("/runs/{run_id}", "get"): {"400", "404"},
            ("/runs/{run_id}/diagnoses", "post"): {"400", "404"},
        }
        for (path, method), status_codes in expected.items():
            with self.subTest(path=path, method=method):
                documented = set(paths[path][method]["responses"])
                self.assertTrue(status_codes <= documented)

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
                "benchmark/metamodels/additional_models/ETL_model/Graph.ecore",
                "benchmark/metamodels/additional_models/ETL_model/Tree.ecore",
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

    def test_a_run_must_fix_the_language_and_task_it_reports(self) -> None:
        for missing in ("language", "task"):
            with self.subTest(missing=missing):
                partial = {key: value for key, value in IDENTITY.items() if key != missing}
                response = self.client.post("/runs", json={**partial, "run_id": f"svc-no-{missing}"})
                self.assertEqual(422, response.status_code)

    def test_a_generation_axis_no_stage_uses_is_recorded_as_null(self) -> None:
        """A run mode need not have both generation branches.

        A semantic-tests-only run has no transformation model, and the manifest
        schema already types that axis as nullable: "not applicable to the stages
        this run executes". Null is not "any value" — a stage that needs a null
        axis refuses, which ``fixed_selection`` covers in test_run_identity.
        """
        transformation_axes = (
            "transformation_model",
            "transformation_strategy",
        )
        partial = {
            key: value for key, value in IDENTITY.items() if key not in transformation_axes
        }
        created = self.client.post("/runs", json={**partial, "run_id": "svc-tests-only"})
        self.assertEqual(200, created.status_code)

        manifest = self.client.get("/runs/svc-tests-only").json()["manifest"]
        for axis in transformation_axes:
            self.assertIsNone(manifest[axis])
        self.assertEqual("gpt-5", manifest["test_generation_model"])

    def test_an_identity_axis_cannot_be_blanked_instead_of_omitted(self) -> None:
        """Empty is not the same statement as "not applicable"."""
        response = self.client.post(
            "/runs",
            json=run_payload(run_id="svc-blank", transformation_model=""),
        )
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
        # The verdict is what downstream work consumes, so it is stored in its
        # own area keyed by the run, not among that run's working state.
        self.assertEqual(
            "svc-diagnosis/attempt-001/diagnosis.json",
            first.json()["artifact"],
        )
        self.assertEqual("gpt-5", first.json()["model"])
        self.assertEqual(2, second.json()["attempt"])

        artifact = self._diagnoses.joinpath(first.json()["artifact"])
        self.assertTrue(artifact.is_file())
        self.assertEqual("openai", read_json(artifact)["provider"])
        # A consumer never has to open the run directory to find it.
        self.assertFalse(
            (Path(self._tmp.name) / "svc-diagnosis" / "responses" / "failure-diagnosis").exists()
        )

    def _failing_execution(self, run_id: str, index: dict[str, object]):
        """Drive one failing execution stage with a prepared diagnosis index."""
        self.client.post("/runs", json=run_payload(run_id=run_id))
        with (
            patch(
                "llm4mtl.stage_service.app._orchestrator.prepare_workspace",
                return_value=Path(self._tmp.name) / "workspace",
            ),
            patch(
                "llm4mtl.stage_service.app._orchestrator.transformations.semantic_validation",
                return_value=StageResult(
                    "transformation_validation",
                    "failed",
                    {"evaluated": 1, "failed": 1},
                    {},
                ),
            ),
            patch(
                "llm4mtl.stage_service.app.prepare_after_execution_stage",
                return_value=index,
            ),
        ):
            return self.client.post(f"/runs/{run_id}/stages/execution", json={})

    def _write_report(self, name: str, *, available: bool) -> str:
        """One prepared failure report, named by its absolute path."""
        report = Path(self._tmp.name) / f"{name}.json"
        write_json(
            report,
            {
                "report_type": "semantic_test_case_failure",
                "source_diagnosis": {
                    "eligible": True,
                    "evidence_bundle": {
                        "structured_actual_vs_expected_difference": {
                            "available": available,
                        }
                    },
                },
            },
        )
        return str(report)

    def test_execution_exposes_the_first_diagnosable_failure_report(self) -> None:
        """The selected report is the first the run recorded as diagnosable.

        A refused report was never written and an ineligible one must not be
        diagnosed. Order is the recorded one — pairs as the execution evidence
        listed them, reports as Surefire reported the failures — so the same
        attempt always selects the same report.
        """
        # Each rejected report gets its own path, so picking the wrong one for
        # the wrong reason cannot still satisfy the assertion.
        refused = self._write_report("refused", available=True)
        ineligible = self._write_report("ineligible", available=True)
        selected = self._write_report("diagnosable", available=True)
        later = self._write_report("later", available=True)
        index = {
            "attempt": 1,
            "pairs": [
                {
                    "reports": [
                        # Preparation names no file when it refuses a report.
                        # One is named here anyway, so a refused entry stays
                        # skipped even if it ever starts carrying a path.
                        {
                            "status": "refused",
                            "detail": "no matching case",
                            "report": refused,
                        },
                        {"status": "created", "eligible": False, "report": ineligible},
                    ]
                },
                {"reports": [{"status": "created", "eligible": True, "report": selected}]},
                {"reports": [{"status": "created", "eligible": True, "report": later}]},
            ],
        }

        response = self._failing_execution("svc-exec-diagnosable", index)
        self.assertEqual(200, response.status_code)
        artifacts = response.json()["artifacts"]
        self.assertEqual(selected, artifacts["failure_report_path"])
        self.assertIn("failure_report_index", artifacts)

    def test_a_report_without_a_model_comparison_is_still_diagnosable(self) -> None:
        """An unavailable comparator difference does not disqualify a report.

        No comparator produces the model-level difference yet. Requiring it
        would reject every real report and leave what the run did observe — the
        JUnit expected/actual pair, the target-model snapshots, the recorded
        exception — unused, which is the whole evidence base Source Diagnosis
        exists to reason over.
        """
        unavailable = self._write_report("no-difference", available=False)
        index = {
            "attempt": 1,
            "pairs": [
                {"reports": [{"status": "created", "eligible": True, "report": unavailable}]}
            ],
        }

        response = self._failing_execution("svc-exec-no-difference", index)
        self.assertEqual(
            unavailable, response.json()["artifacts"]["failure_report_path"]
        )

    def test_execution_omits_the_report_path_when_none_is_diagnosable(self) -> None:
        """A missing key is the honest answer: there is nothing to diagnose.

        The index is still named, so a caller can read why every report was
        refused instead of having to guess that preparation ran at all.
        """
        index = {
            "attempt": 1,
            "pairs": [
                {
                    "reports": [
                        {"status": "refused", "detail": "no matching case"},
                        {
                            "status": "created",
                            "eligible": False,
                            "report": self._write_report("ineligible", available=True),
                        },
                    ]
                }
            ],
        }

        response = self._failing_execution("svc-exec-undiagnosable", index)
        artifacts = response.json()["artifacts"]
        self.assertNotIn("failure_report_path", artifacts)
        self.assertIn("failure_report_index", artifacts)

    def test_prepared_evidence_references_stay_out_of_the_recorded_result(self) -> None:
        """Where evidence lives is orchestration, not a recorded observation.

        Preparation can only run once the attempt has claimed its number, so the
        references reach the caller through the response while ``result.json``
        keeps exactly the contract it was validated against. Both paths stay
        re-derivable from the run directory, so nothing is lost.
        """
        index = {
            "attempt": 1,
            "pairs": [
                {
                    "reports": [
                        {
                            "status": "created",
                            "eligible": True,
                            "report": self._write_report("recorded", available=True),
                        }
                    ]
                }
            ],
        }

        response = self._failing_execution("svc-exec-recorded", index)
        body = response.json()
        self.assertIn("failure_report_path", body["artifacts"])

        recorded = read_json(
            Path(self._tmp.name)
            / "svc-exec-recorded"
            / "stages"
            / "execution"
            / "attempts"
            / "attempt-001"
            / "result.json"
        )
        self.assertNotIn("failure_report_path", recorded["artifacts"])
        self.assertNotIn("failure_report_index", recorded["artifacts"])
        # The stage facts the attempt recorded are the ones the caller reads.
        self.assertEqual(recorded["outcome_code"], body["outcome_code"])
        self.assertEqual(recorded["status"], body["status"])
        self.assertEqual(recorded["counts"], body["counts"])

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
