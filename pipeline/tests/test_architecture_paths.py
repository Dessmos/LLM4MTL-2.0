from __future__ import annotations

import json
import re
import unittest
from copy import deepcopy

from llm4mtl.conventions import (
    LANGUAGE_CONFIGS,
    n8n_workflows_root,
    repo_root,
    task_prompt_candidates_root,
)
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.paths import MIGRATION_MAP, REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.n8n_exports import (
    INPUTS,
    MODELS,
    PROMPT_INPUT_NODE,
    PROVIDER_MODEL_IDS,
    STRATEGIES,
    synchronize_prompt_generation,
    synchronize_test_generation,
    synchronize_transformation_generation,
)

# Transformation generation is a full model x strategy grid per language. The
# Reactions grid is driven by one matrix workflow instead of twelve exports.
TRANSFORMATION_MODELS = tuple(model for model in MODELS if model != "qwen2-5-coder-7b")
EXPECTED_TRANSFORMATION_WORKFLOWS = {
    (language, model, strategy)
    for language in ("atl", "etl", "qvto")
    for model in TRANSFORMATION_MODELS
    for strategy in STRATEGIES
}


_WORKFLOW_NAME = re.compile(
    r"Prompting_([A-Za-z]+)_(.+?)_(few_shots_AND_grammar|only_prompt|few_shot|grammar)"
    r"\.json"
)


def _identity_from_name(file_name: str) -> tuple[str, str, str]:
    match = _WORKFLOW_NAME.fullmatch(file_name)
    assert match is not None, file_name
    language, model, strategy = match.groups()
    return language.lower(), model, strategy


def _nested_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested in value.values():
            strings.extend(_nested_strings(nested))
        return strings
    if isinstance(value, list):
        strings = []
        for nested in value:
            strings.extend(_nested_strings(nested))
        return strings
    return []


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
        self.assertIn(
            '"../../../prompt_assets/tests/helper_methods:/data/helper_methods:ro"',
            text,
        )
        self.assertIn("stage-service:", text)
        self.assertNotIn(
            '"../../../benchmark/metamodels:/data/models:ro"',
            text,
        )
        self.assertNotIn("/data/snippets", text)
        self.assertNotIn("/data/baseline", text)

    def test_n8n_compose_allows_only_the_mounted_workflow_workspace(self) -> None:
        for workflow_kind in ("tests", "transformations"):
            compose = TARGET.workflows / workflow_kind / "docker-compose.yml"
            text = compose.read_text(encoding="utf-8")
            with self.subTest(workflow_kind=workflow_kind):
                self.assertIn("N8N_RESTRICT_FILE_ACCESS_TO=/data", text)

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
                candidates = task_prompt_candidates_root(config).relative_to(
                    TARGET.artifacts_work
                )
                expected_output = (
                    f"=/data/artifacts/{candidates.as_posix()}/{model}/"
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

    def test_every_prompt_asset_is_read_from_its_language_directory(self) -> None:
        """No workflow may read another language's assets, or a whole tree.

        ``/data/helper_methods//*`` used to glob the language directories
        instead of the files in them, in 91 of the 93 workflows.
        """
        for workflow in sorted(TARGET.workflows.rglob("*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "nodes" not in payload:
                continue
            for node in payload["nodes"]:
                selector = node.get("parameters", {}).get("fileSelector")
                if not isinstance(selector, str):
                    continue
                match = re.search(
                    r"/data/(helper_methods|examples|grammar|task_prompts)/([^/]*)/",
                    selector,
                )
                if match is None:
                    continue
                with self.subTest(workflow=workflow, node=node["name"]):
                    self.assertIn(match.group(2), LANGUAGE_CONFIGS, selector)

    def test_optional_asset_references_are_guarded_by_execution(self) -> None:
        optional_assets = (
            "Extract text from examples file",
            "Extract text from grammar",
            "Extract text from helper methods",
        )
        for workflow in sorted(TARGET.workflows.rglob("*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "nodes" not in payload:
                continue
            for node in payload["nodes"]:
                for expression in _nested_strings(node.get("parameters", {})):
                    for asset_node in optional_assets:
                        double_quoted_reference = f'$("{asset_node}").item'
                        single_quoted_reference = f"$('{asset_node}').item"
                        if (
                            double_quoted_reference not in expression
                            and single_quoted_reference not in expression
                        ):
                            continue
                        with self.subTest(
                            workflow=workflow,
                            node=node["name"],
                            asset_node=asset_node,
                        ):
                            self.assertTrue(
                                (
                                    f'$("{asset_node}").isExecuted'
                                    in expression
                                )
                                or (
                                    f"$('{asset_node}').isExecuted"
                                    in expression
                                )
                            )

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

    def test_every_workflow_asks_its_provider_for_the_same_model(self) -> None:
        """One provider-side identifier per model, and no dead provider nodes.

        QVT-O's Gemini exports asked for ``models/gemini-2-5-pro``, which is not
        a Google model id; ETL's and ATL's asked for ``models/gemini-2.5-pro``.
        Separately, exports carried provider nodes with no ``ai_languageModel``
        connection, so a gpt-5 workflow appeared to need three credentials.
        """
        for workflow in sorted(TARGET.workflows.rglob("*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "nodes" not in payload:
                continue
            connections = payload.get("connections", {})
            wired = {
                name
                for name, outputs in connections.items()
                if any(targets for targets in outputs.get("ai_languageModel", []))
            }
            for node in payload["nodes"]:
                if "lmChat" not in node.get("type", ""):
                    continue
                with self.subTest(workflow=workflow.name, node=node["name"]):
                    self.assertIn(node["name"], wired)
                    pinned = PROVIDER_MODEL_IDS.get(node["type"])
                    if pinned is not None:
                        self.assertEqual(pinned, node["parameters"]["modelName"])

    def test_frozen_task_prompts_carry_no_export_artefacts(self) -> None:
        """The frozen file is verbatim prompt text and nothing else.

        Every one of them used to end with a stray "+" left by the export step.
        It reached both downstream generators and the provenance hash.
        """
        for prompt in sorted(
            (TARGET.prompt_assets / "task_prompts").rglob("*.txt")
        ):
            text = prompt.read_text(encoding="utf-8")
            with self.subTest(prompt=prompt.name):
                self.assertTrue(text.strip())
                self.assertTrue(text.endswith("\n"))
                self.assertFalse(text.strip().endswith("+"))

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
        # Exactly one per language, each in its own <lang>_variants directory.
        # Copies used to sit at the workflows root as well, so "the" ATL prompt
        # workflow existed twice and could drift.
        self.assertEqual(len(LANGUAGE_CONFIGS), prompt_generation_checked)
        for language in LANGUAGE_CONFIGS:
            with self.subTest(language=language):
                self.assertTrue(
                    (
                        root
                        / f"{language}_variants"
                        / f"Prompt_generation_{language}.json"
                    ).is_file()
                )

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
        self.assertEqual(len(EXPECTED_TRANSFORMATION_WORKFLOWS), checked)

    def test_transformation_workflows_use_one_model_and_strategy_vocabulary(
        self,
    ) -> None:
        """File name, workflow name, and response path must agree everywhere.

        QVT-O used to spell its models ``gpt5``/``claude``/``gemini`` and its
        strategies ``zero_shot``/``few_shot_AND_grammar``. The response path is
        what selects a strategy, so a QVT-O run could never be matched against
        the ``few_shots_AND_grammar`` the experiment matrices declare.
        """
        root = TARGET.workflows / "transformations" / "workflows"
        found = set()
        for workflow in sorted(root.rglob("Prompting_*.json")):
            payload = json.loads(workflow.read_text(encoding="utf-8"))
            nodes = {node["name"]: node for node in payload.get("nodes", [])}
            if "(Re-)Generate code" not in nodes:
                continue
            language, model, strategy = _identity_from_name(workflow.name)
            output = next(
                node["parameters"]["fileName"]
                for node in payload["nodes"]
                if node.get("parameters", {}).get("fileName")
            )
            with self.subTest(workflow=workflow.name):
                self.assertIn(model, MODELS)
                self.assertIn(strategy, STRATEGIES)
                self.assertEqual(f"{language.upper()}_{model}_{strategy}", payload["name"])
                self.assertIn(
                    f"/transformation_generation/{language}/responses/"
                    f"{model}/{strategy}/",
                    output,
                )
            found.add((language, model, strategy))
        self.assertEqual(EXPECTED_TRANSFORMATION_WORKFLOWS, found)

    def test_the_reactions_matrix_declares_the_shared_strategies(self) -> None:
        matrix = json.loads(
            (
                TARGET.workflows
                / "transformations/workflows/updated_reactions_workflow"
                / "generate_reactions"
                / "LLM4MTL_Generate_Reactions_for_all_Configurations.json"
            ).read_text(encoding="utf-8")
        )
        declared = next(
            json.loads(node["parameters"]["jsonOutput"])["strategies"]
            for node in matrix["nodes"]
            if node["name"] == "Define Strategies"
        )
        self.assertEqual(
            sorted(STRATEGIES),
            sorted(strategy["name"] for strategy in declared),
        )
        # Shared assets come from /data like every other workflow's; this one
        # used to read them from a /home/node/.n8n-files path nothing mounts.
        self.assertNotIn("n8n-files", json.dumps(matrix))

    def test_transformation_generation_reaches_the_frozen_prompt_matrix(self) -> None:
        root = TARGET.workflows / "transformations" / "workflows"

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
