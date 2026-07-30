from __future__ import annotations

import json
import re
import unittest
from copy import deepcopy

from llm4mtl.conventions import LANGUAGE_CONFIGS, n8n_workflows_root, repo_root
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.paths import MIGRATION_MAP, REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.n8n_exports import (
    INPUTS,
    MODELS,
    PROMPT_INPUT_NODE,
    synchronize_prompt_generation,
    synchronize_test_generation,
    synchronize_transformation_generation,
)


class ActivePathTests(unittest.TestCase):
    def test_active_runtime_uses_existing_repository_root(self) -> None:
        self.assertEqual(REPO_ROOT, repo_root())
        self.assertEqual(REPO_ROOT, ExperimentOrchestrator().repo_root)
        self.assertTrue(REPO_ROOT.is_dir())

    def test_target_layout_matches_migrated_directories(self) -> None:
        self.assertEqual(REPO_ROOT / "prompt_assets", TARGET.prompt_assets)
        self.assertTrue(TARGET.prompt_assets.is_dir())
        self.assertEqual(
            TARGET.package / "transformation_execution",
            MIGRATION_MAP["pipeline/transformation_validation"][1],
        )
        self.assertEqual(TARGET.workflows / "tests", MIGRATION_MAP["n8n/tests"][1])


class N8nWorkflowTests(unittest.TestCase):
    def test_connections_reference_existing_nodes(self) -> None:
        for workflow in sorted(TARGET.workflows.rglob("*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "nodes" not in payload:
                continue
            names = {node["name"] for node in payload["nodes"]}
            connections = payload.get("connections", {})
            sources = set(connections)
            targets: set[str] = set()
            self._collect_connection_targets(connections, targets)
            with self.subTest(workflow=workflow):
                self.assertLessEqual(sources | targets, names)

    def test_test_generation_model_mount_preserves_language_directory(self) -> None:
        compose = TARGET.workflows / "tests" / "docker-compose.yml"
        text = compose.read_text(encoding="utf-8")
        self.assertIn(
            '"../../../benchmark/tasks:/data/benchmark/tasks:ro"',
            text,
        )
        self.assertIn(
            '"../../../prompt_assets/task_prompts:/data/task_prompts:ro"',
            text,
        )
        self.assertIn("stage-service:", text)
        self.assertNotIn(
            '"../../../benchmark/metamodels:/data/models:ro"',
            text,
        )
        self.assertNotIn("/data/snippets", text)
        self.assertNotIn("/data/baseline", text)

    def test_prompt_generation_is_the_first_llm_stage_for_every_language(self) -> None:
        for language, config in LANGUAGE_CONFIGS.items():
            root = n8n_workflows_root(config) / "prompt_generation"
            for model in MODELS:
                workflow = (
                    root
                    / f"Prompt_generation_tests_{config.workflow_language}_{model}.json"
                )
                payload = json.loads(workflow.read_text(encoding="utf-8"))
                nodes = {node["name"]: node for node in payload["nodes"]}
                serialized = json.dumps(payload)
                generation_name = (
                    "Generate Prompt with local Qwen"
                    if model == "qwen2-5-coder-7b"
                    else "Generate Prompt from Input"
                )
                expected_output = (
                    "=/data/artifacts/task_prompt_candidates/"
                    f"{language}/{model}/"
                    f'{{{{ $node["Save reaction name"].json.baseName }}}}.txt'
                )
                if "Save reaction name" not in nodes:
                    expected_output = expected_output.replace(
                        "Save reaction name",
                        "Save file name",
                    )

                with self.subTest(language=language, model=model):
                    self.assertIn(generation_name, nodes)
                    self.assertEqual(
                        (
                            "=/data/benchmark/tasks/"
                            f"{language}/references/*."
                            f"{INPUTS[language].reference_extension}"
                        ),
                        nodes["Read reference file"]["parameters"][
                            "fileSelector"
                        ],
                    )
                    self.assertNotIn("Read model files", nodes)
                    self.assertIn(PROMPT_INPUT_NODE, nodes)
                    self.assertEqual(
                        "http://stage-service:8129/prompt-inputs/resolve",
                        nodes[PROMPT_INPUT_NODE]["parameters"]["url"],
                    )
                    self.assertTrue(
                        list(
                            (
                                TARGET.benchmark
                                / "tasks"
                                / language
                                / "references"
                            ).glob(
                                f"*.{INPUTS[language].reference_extension}"
                            )
                        )
                    )
                    self.assertEqual(
                        expected_output,
                        nodes["Write prompt to disk"]["parameters"]["fileName"],
                    )
                    self.assertIn("natural-language task prompt", serialized)
                    self.assertIn("metamodel_text", serialized)
                    self.assertNotIn("semantic_cases.json", serialized)
                    self.assertNotIn("concatenated_model", serialized)
                    self.assertNotIn("prompt_drafts", serialized)
                    self.assertNotIn("prompts_smoke", serialized)
                    self.assertNotIn("writes drafts only", serialized)
                    self.assertEqual(
                        payload,
                        synchronize_prompt_generation(
                            deepcopy(payload),
                            language,
                            model,
                        ),
                    )
                    if language == "reactions":
                        self.assertIn("reaction-triggered change", serialized)
                        self.assertIn("propagated effect", serialized)

    def test_test_generation_consumes_the_shared_frozen_prompt(self) -> None:
        for language, config in LANGUAGE_CONFIGS.items():
            root = n8n_workflows_root(config) / "test_generation"
            for workflow in sorted(root.glob("*.json")):
                payload = json.loads(workflow.read_text(encoding="utf-8"))
                nodes = {node["name"]: node for node in payload["nodes"]}
                serialized = json.dumps(payload)
                output = nodes["Write response to disk"]["parameters"]["fileName"]
                identity = re.search(r"/responses/([^/]+)/([^/]+)/", output)
                self.assertIsNotNone(identity)
                model, _ = identity.groups()
                prompt_node_name = (
                    "Read Qwen prompt files"
                    if "Read Qwen prompt files" in nodes
                    else "Read prompt files"
                )

                with self.subTest(workflow=workflow):
                    self.assertEqual(
                        f"=/data/task_prompts/{language}/*.txt",
                        nodes[prompt_node_name]["parameters"]["fileSelector"],
                    )
                    self.assertNotIn("Read model files", nodes)
                    self.assertIn(PROMPT_INPUT_NODE, nodes)
                    self.assertIn("metamodel_text", serialized)
                    self.assertNotIn("concatenated_model", serialized)
                    self.assertTrue(output.endswith(".md"))
                    self.assertNotIn("prompts_smoke", serialized)
                    self.assertNotIn(
                        "expert Java/JUnit test engineer",
                        serialized,
                    )
                    self.assertEqual(
                        payload,
                        synchronize_test_generation(
                            deepcopy(payload),
                            language,
                        ),
                    )
                    if language == "reactions":
                        self.assertIn("change_propagation", serialized)
                        self.assertIn("tests[].changes", serialized)

    def test_frozen_task_prompts_cover_every_task_exactly_once(self) -> None:
        for language, inputs in INPUTS.items():
            references = {
                path.stem
                for path in (
                    TARGET.benchmark / "tasks" / language / "references"
                ).glob(f"*.{inputs.reference_extension}")
            }
            contracts = {
                path.stem
                for path in (
                    TARGET.benchmark / "tasks" / language / "task_contracts"
                ).glob("*.json")
            }
            prompts = {
                path.stem
                for path in (
                    TARGET.prompt_assets / "task_prompts" / language
                ).glob("*.txt")
            }
            with self.subTest(language=language):
                self.assertEqual(references, contracts)
                self.assertEqual(references, prompts)

    def test_transformation_generation_uses_the_same_frozen_prompts(self) -> None:
        root = TARGET.workflows / "transformations" / "workflows"
        prompt_generation_checked = 0
        for workflow in sorted(root.rglob("Prompt_generation*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            nodes = {node["name"]: node for node in payload.get("nodes", [])}
            if "Generate Prompt from Input" not in nodes:
                continue
            serialized = json.dumps(payload)
            with self.subTest(workflow=workflow):
                self.assertIn(PROMPT_INPUT_NODE, nodes)
                self.assertNotIn("Read model files", nodes)
                self.assertNotIn("concatenated_model", serialized)
                self.assertIn("/task_prompt_candidates/", serialized)
            prompt_generation_checked += 1
        self.assertEqual(5, prompt_generation_checked)

        checked = 0
        for workflow in sorted(root.rglob("Prompting*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            nodes = {node["name"]: node for node in payload.get("nodes", [])}
            if "(Re-)Generate code" not in nodes:
                continue
            selector = nodes["Read prompt files"]["parameters"]["fileSelector"]
            language = re.search(r"/task_prompts/([^/]+)/", selector).group(1)
            serialized = json.dumps(payload)
            with self.subTest(workflow=workflow):
                self.assertEqual(
                    f"=/data/task_prompts/{language}/*.txt",
                    selector,
                )
                self.assertIn(PROMPT_INPUT_NODE, nodes)
                self.assertNotIn("Read model files", nodes)
                self.assertIn("metamodel_text", serialized)
                self.assertNotIn("concatenated_model", serialized)
                self.assertEqual(
                    payload,
                    synchronize_transformation_generation(
                        deepcopy(payload),
                        language,
                    ),
                )
            checked += 1
        self.assertEqual(40, checked)

        matrix_path = (
            root
            / "updated_reactions_workflow"
            / "generate_reactions"
            / "LLM4MTL_Generate_Reactions_for_all_Configurations.json"
        )
        matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        matrix_nodes = {node["name"]: node for node in matrix["nodes"]}
        serialized_matrix = json.dumps(matrix)
        self.assertEqual(
            "=/data/task_prompts/reactions/*.txt",
            matrix_nodes["Read prompt files"]["parameters"]["fileSelector"],
        )
        self.assertIn(PROMPT_INPUT_NODE, matrix_nodes)
        self.assertNotIn("Read model files", matrix_nodes)
        self.assertIn("metamodel_text", serialized_matrix)
        self.assertNotIn("concatenated_model", serialized_matrix)

    @classmethod
    def _collect_connection_targets(cls, value: object, result: set[str]) -> None:
        if isinstance(value, dict):
            node = value.get("node")
            if isinstance(node, str):
                result.add(node)
            for nested in value.values():
                cls._collect_connection_targets(nested, result)
        elif isinstance(value, list):
            for nested in value:
                cls._collect_connection_targets(nested, result)


if __name__ == "__main__":
    unittest.main()
