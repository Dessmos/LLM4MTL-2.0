"""Four-language adapter coverage and opt-in real-engine walking skeletons."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.conventions import language_config
from llm4mtl.domain import ArtifactValidation, GeneratedSuite
from llm4mtl.experiment_runner.config import load_mapping
from llm4mtl.experiment_runner.matrix import expand_matrix
from llm4mtl.languages import (
    REQUIRED_LANGUAGES,
    LanguageAdapter,
    Workspace,
    implemented_languages,
    language_adapter,
)
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.suite_execution import (
    GENERATED_TRANSFORMATION_ROLE,
    record_observation,
)
from llm4mtl.task_contracts.build_language_task_contracts import (
    build_atl_contract,
    build_qvto_contract,
    build_reactions_contract,
)
from llm4mtl.transformation_execution.hashing import file_sha256
from llm4mtl.workspace import materialize_engine

SKELETONS = {
    "etl": "Tree2Graph",
    "atl": "NetworkToGraph_All",
    "qvto": "Mappings",
    "reactions": "FamiliesToPersons_InsertedFamilyRegister",
}
FIXTURES = TARGET.pipeline / "tests/fixtures/walking_skeletons"


class FourLanguageCoverageTests(unittest.TestCase):
    def test_registry_contains_exactly_the_four_required_adapters(self) -> None:
        self.assertEqual(tuple(sorted(REQUIRED_LANGUAGES)), implemented_languages())
        for language in REQUIRED_LANGUAGES:
            with self.subTest(language=language):
                adapter = language_adapter(language)
                self.assertIsInstance(adapter, LanguageAdapter)
                self.assertEqual(language, adapter.language_id)

    def test_every_matrix_task_is_data_complete(self) -> None:
        for language in REQUIRED_LANGUAGES:
            with self.subTest(language=language):
                matrix = _matrix(language)
                tasks = set(matrix["tasks"])
                config = language_config(language)
                references = {
                    path.stem
                    for path in (
                        TARGET.benchmark / "tasks" / language / "references"
                    ).glob(f"*{language_adapter(language).reference_transformation('_').suffix}")
                    if path.name != ".gitkeep"
                }
                contracts = {
                    path.stem
                    for path in (
                        TARGET.benchmark / "tasks" / language / "task_contracts"
                    ).glob("*.json")
                }
                self.assertTrue(tasks <= references)
                self.assertTrue(tasks <= contracts)
                if language != "etl":
                    self.assertEqual(tasks, references)
                    self.assertEqual(tasks, contracts)
                self.assertTrue(
                    (TARGET.prompt_assets / f"tests/grammar/{language}/EBNF.txt").is_file()
                )
                self.assertTrue(
                    (
                        TARGET.prompt_assets
                        / f"tests/few_shot/{config.language_key}/test_generation_examples.txt"
                    ).is_file()
                )
                for model in matrix["test_models"]:
                    for strategy in matrix["test_strategies"]:
                        workflow = (
                            TARGET.workflows
                            / "tests"
                            / "workflows"
                            / f"{language}_variants"
                            / "test_generation"
                            / (
                                f"Prompting_tests_{config.workflow_language}_"
                                f"{model}_{strategy}.json"
                            )
                        )
                        self.assertTrue(workflow.is_file(), workflow)
                for task in tasks:
                    contract_path = (
                        TARGET.benchmark
                        / "tasks"
                        / language
                        / "task_contracts"
                        / f"{task}.json"
                    )
                    contract_payload = json.loads(
                        contract_path.read_text(encoding="utf-8")
                    )
                    validate_artifact(
                        "contract",
                        contract_payload,
                    )
                    if language != "etl":
                        for model in contract_payload["models"]:
                            self.assertIn("typesUsedInTransformation", model)
                            self.assertNotIn("typesUsedInEtL", model)
                run_specs = expand_matrix(matrix)
                self.assertTrue(run_specs)
                self.assertEqual(len(run_specs), len({spec.run_id for spec in run_specs}))
                self.assertEqual({language}, {spec.language for spec in run_specs})

    def test_all_four_structured_fixtures_render_deterministically(self) -> None:
        for language, task in SKELETONS.items():
            with self.subTest(language=language, task=task):
                adapter = language_adapter(language)
                extracted = _fixture_files(language, task)
                first, first_validation = adapter.render_suite_artifacts(
                    task, extracted
                )
                second, second_validation = adapter.render_suite_artifacts(
                    task, extracted
                )
                self.assertEqual(ArtifactValidation(valid=True, contract_applied=True), first_validation)
                self.assertEqual(first_validation, second_validation)
                self.assertEqual(first, second)
                self.assertEqual(1, len([name for name in first if name.endswith(".java")]))
                self.assertIn(
                    adapter.reference_transformation(task).suffix,
                    json.loads(first["semantic_cases.json"])["transformation"],
                )

    def test_non_etl_contracts_are_reproducible_from_protected_inputs(self) -> None:
        builders = {
            "atl": build_atl_contract,
            "qvto": build_qvto_contract,
            "reactions": build_reactions_contract,
        }
        for language, builder in builders.items():
            references = TARGET.benchmark / "tasks" / language / "references"
            contracts = TARGET.benchmark / "tasks" / language / "task_contracts"
            for reference in sorted(references.iterdir()):
                if not reference.is_file():
                    continue
                with self.subTest(language=language, task=reference.stem):
                    expected = json.loads(
                        (contracts / f"{reference.stem}.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(expected, builder(reference))

    def test_qvto_two_output_slots_remain_distinct(self) -> None:
        spec = {
            "schemaVersion": "1.0",
            "tests": [
                {
                    "name": "two_outputs",
                    "models": [
                        {
                            "name": "m",
                            "kind": "emf",
                            "role": "source",
                            "path": "models/in.ecore",
                            "generated": True,
                            "metamodelUri": "http://www.eclipse.org/emf/2002/Ecore",
                        },
                        {
                            "name": "x",
                            "kind": "emf",
                            "role": "target",
                            "generated": False,
                            "metamodelUri": "http://www.eclipse.org/emf/2002/Ecore",
                        },
                        {
                            "name": "y",
                            "kind": "emf",
                            "role": "target",
                            "generated": False,
                            "metamodelUri": "http://www.eclipse.org/emf/2002/Ecore",
                        },
                    ],
                    "assertions": [
                        {
                            "kind": "count",
                            "model": "x",
                            "type": "EPackage",
                            "expected": 1,
                        },
                        {
                            "kind": "count",
                            "model": "y",
                            "type": "EPackage",
                            "expected": 1,
                        },
                    ],
                }
            ],
        }
        extracted = {
            "semantic_cases.json": json.dumps(spec),
            "models/in.ecore": (
                FIXTURES / "qvto/Mappings/models/in.ecore"
            ).read_text(encoding="utf-8"),
        }
        rendered, validation = language_adapter("qvto").render_suite_artifacts(
            "ModelExtents",
            extracted,
        )
        self.assertTrue(validation.valid, validation.violations)
        normalized = json.loads(rendered["semantic_cases.json"])
        self.assertEqual(
            ["m", "x", "y"],
            [model["runtimeName"] for model in normalized["tests"][0]["models"]],
        )
        java = next(
            content for path, content in rendered.items() if path.endswith(".java")
        )
        self.assertIn("executeTransformation2Outputs", java)
        self.assertIn("outputs[1]", java)


@unittest.skipUnless(
    os.environ.get("LLM4MTL_RUN_ENGINE_TESTS") == "1",
    "set LLM4MTL_RUN_ENGINE_TESTS=1 for real parser and Maven walking skeletons",
)
class RealEngineWalkingSkeletonTests(unittest.TestCase):
    def test_each_language_runs_reference_and_generated_paths(self) -> None:
        for language, task in SKELETONS.items():
            with self.subTest(language=language, task=task):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    adapter = language_adapter(language)
                    suite = _render_suite(root / "suite", language, task, adapter)
                    engine_dir = materialize_engine(
                        TARGET.engine_harness(language),
                        root / "workspaces",
                        f"{language}-harness",
                    )
                    workspace = Workspace(
                        engine_dir=engine_dir,
                        observations_dir=root / "evidence",
                    )
                    reference = adapter.reference_transformation(task)
                    generated = (
                        root
                        / "generated"
                        / f"{task}{reference.suffix}"
                    )
                    generated.parent.mkdir(parents=True)
                    shutil.copyfile(reference, generated)

                    parse = adapter.parse_transformations(
                        [reference, generated],
                        workspace,
                    )
                    self.assertTrue(parse[reference].parsed, parse[reference].diagnostic)
                    self.assertTrue(parse[generated].parsed, parse[generated].diagnostic)

                    reference_observation = adapter.execute_suite(
                        suite, reference, workspace, 1200
                    )
                    self.assertTrue(
                        reference_observation.is_technically_executable,
                        reference_observation.error_summary,
                    )
                    self.assertTrue(
                        reference_observation.is_reference_valid,
                        reference_observation.error_summary,
                    )
                    evidence_path = record_observation(
                        workspace.observations_dir,
                        suite,
                        reference,
                        reference_observation,
                    )
                    self.assertTrue(evidence_path.is_file())

                    generated_root = (
                        workspace.observations_dir
                        / "generated_transformations"
                        / file_sha256(generated)
                    )
                    generated_observation = adapter.execute_suite(
                        suite,
                        generated,
                        Workspace(
                            engine_dir=engine_dir,
                            observations_dir=generated_root,
                        ),
                        1200,
                    )
                    self.assertTrue(
                        generated_observation.is_reference_valid,
                        generated_observation.error_summary,
                    )
                    generated_evidence = record_observation(
                        generated_root,
                        suite,
                        generated,
                        generated_observation,
                        transformation_role=GENERATED_TRANSFORMATION_ROLE,
                    )
                    self.assertTrue(generated_evidence.is_file())
                    generated_payload = json.loads(
                        generated_evidence.read_text(encoding="utf-8")
                    )
                    self.assertEqual(
                        GENERATED_TRANSFORMATION_ROLE,
                        generated_payload["inputs"]["transformation"]["role"],
                    )
                    if language in {"atl", "qvto", "reactions"}:
                        self.assertTrue(
                            any(
                                (workspace.observations_dir / "snapshots").glob("*.xmi")
                            )
                        )
                        self.assertTrue(
                            any(
                                (
                                    generated_root / "snapshots"
                                ).glob("*.xmi")
                            )
                        )


def _matrix(language: str) -> dict[str, Any]:
    if language == "etl":
        matrix = TARGET.experiments / "matrices/thesis-ablation.yaml"
    else:
        matrix = TARGET.experiments / f"matrices/thesis-{language}.yaml"
    return load_mapping(matrix)


def _fixture_files(language: str, task: str) -> dict[str, str]:
    root = FIXTURES / language / task
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _render_suite(
    destination: Path,
    language: str,
    task: str,
    adapter: LanguageAdapter,
) -> GeneratedSuite:
    files, validation = adapter.render_suite_artifacts(
        task,
        _fixture_files(language, task),
    )
    if not validation.valid:
        raise AssertionError(validation.violations)
    destination.mkdir(parents=True)
    for relative, content in files.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (destination / "metadata.json").write_text(
        json.dumps({"artifact_validation": validation.as_metadata()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    suite = GeneratedSuite(
        language,
        destination,
        task,
        "walking-skeleton",
        "deterministic",
        "suite_001",
    )
    static_validation = adapter.validate_suite_artifacts(suite)
    if not static_validation.valid:
        raise AssertionError(static_validation.violations)
    return suite


if __name__ == "__main__":
    unittest.main()
