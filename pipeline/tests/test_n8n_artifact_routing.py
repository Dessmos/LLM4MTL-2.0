from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_ROOT = REPOSITORY_ROOT / "workflows" / "n8n"


def _workflow_documents() -> list[tuple[Path, dict[str, Any]]]:
    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(WORKFLOWS_ROOT.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("nodes"), list):
            documents.append((path, document))
    return documents


def _connected_models(document: dict[str, Any]) -> list[str]:
    nodes_by_name = {node["name"]: node for node in document["nodes"]}
    models: list[str] = []
    for source_name, connections in document.get("connections", {}).items():
        for output in connections.get("ai_languageModel", []):
            if not output:
                continue
            node = nodes_by_name[source_name]
            parameters = node.get("parameters", {})
            model = parameters.get("model", {}).get("value") or parameters.get("modelName")
            if model:
                models.append(_model_path_alias(model))
    for node in document["nodes"]:
        if node["type"] != "n8n-nodes-base.httpRequest":
            continue
        if "qwen2.5-coder:7b" in json.dumps(node.get("parameters", {})):
            models.append("qwen2-5-coder-7b")
    return models


def _model_path_alias(model: str) -> str:
    if "claude-sonnet-4" in model:
        return "claude-sonnet-4"
    if "gemini-2.5-pro" in model or "gemini-2-5-pro" in model:
        return "gemini-2-5-pro"
    return model


_NODE_REFERENCE = re.compile(r"\$\('([^']+)'\)")


def _writes_inside_artifacts(document: dict[str, Any], file_name: str) -> bool:
    """Whether a write node's target is contained in the artifacts mount.

    A file name is either the literal path or an expression reading a path some
    earlier node built. Following that reference keeps the containment check
    real for both: a node that derives its paths once still has to derive them
    under ``/data/artifacts``.
    """
    if file_name.startswith("=/data/artifacts/"):
        return True
    referenced = _NODE_REFERENCE.search(file_name)
    if referenced is None:
        return False
    source = next(
        (node for node in document["nodes"] if node["name"] == referenced.group(1)),
        None,
    )
    if source is None:
        return False
    return "/data/artifacts/" in json.dumps(source.get("parameters", {}))


class N8nArtifactRoutingTests(unittest.TestCase):
    def test_generated_file_writes_target_artifacts(self) -> None:
        write_count = 0
        for path, document in _workflow_documents():
            for node in document["nodes"]:
                parameters = node.get("parameters", {})
                if (
                    node["type"] == "n8n-nodes-base.readWriteFile"
                    and parameters.get("operation") == "write"
                ):
                    write_count += 1
                    self.assertTrue(
                        _writes_inside_artifacts(
                            document, parameters.get("fileName", "")
                        ),
                        f"{path}: {node['name']} writes outside artifacts",
                    )
                if node["type"] == "n8n-nodes-base.executeCommand":
                    command = parameters.get("command", "")
                    self.assertNotIn("snippets/responses", command, str(path))
                    self.assertNotIn("snippets/out", command, str(path))
        self.assertGreater(write_count, 0)

    def test_write_paths_identify_the_connected_model(self) -> None:
        for path, document in _workflow_documents():
            writes = [
                node["parameters"]["fileName"]
                for node in document["nodes"]
                if node["type"] == "n8n-nodes-base.readWriteFile"
                and node.get("parameters", {}).get("operation") == "write"
            ]
            if len(writes) != 1:
                continue
            models = _connected_models(document)
            if len(models) == 1:
                self.assertIn(models[0], writes[0], str(path))
            elif len(models) > 1:
                self.assertIn("llmName", writes[0], str(path))

    def test_diagnosis_is_persisted_with_provenance(self) -> None:
        path = WORKFLOWS_ROOT / "subworkflows" / "diagnosis" / "llm-diagnosis.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in document["nodes"]}

        validation_code = nodes["Validate Evidence Bundle"]["parameters"]["jsCode"]
        for evidence_field in (
            "original_task_description",
            "relevant_source_and_target_metamodel_constraints",
            "generated_transformation",
            "failing_test_case_or_assertion",
            "input_model",
            "expected_output_or_properties",
            "actual_target_model",
            "structured_actual_vs_expected_difference",
            "generated_execution_summary",
            "reference_transformation_result",
        ):
            self.assertIn(evidence_field, validation_code)
        self.assertIn("parser passed and semantic test failed", validation_code)
        # The bundle Python writes is the contract, and it carries more than a
        # diagnosis reads. Requiring an exact key set made every extra field a
        # hard failure, so presence is what is checked now.
        self.assertNotIn("must contain exactly", validation_code)
        self.assertIn("!(field in bundle)", validation_code)
        # `in`, not truthiness: an assertion failure carries stack_traces: [].
        self.assertNotIn("!bundle[field]", validation_code)
        self.assertNotIn("execution_error_or_log", validation_code)
        # The difference object stays mandatory, but an unavailable one is a
        # legitimate shape: no comparator produces the model-level diff yet, so
        # requiring it would reject every real report. A diff that claims to be
        # available must still be complete.
        self.assertIn("structured_actual_vs_expected_difference", validation_code)
        self.assertIn("typeof difference.available !== 'boolean'", validation_code)
        self.assertIn("difference.available === true &&", validation_code)
        self.assertNotIn("difference.available !== true", validation_code)

        # Every artifact path is derived once and read back by name. Rebuilding
        # one from $json after a Convert to File node resolves it to undefined.
        build_node = "Build Diagnosis Request Artifact"
        build_code = nodes[build_node]["parameters"]["jsCode"]
        for derived in ("artifact_directory", "request_path", "raw_response_path", "result_path"):
            self.assertIn(f"{derived}:", build_code)
        directory = nodes["Create Diagnosis Artifact Directory"]["parameters"]["command"]
        self.assertIn(f"$('{build_node}').first().json.artifact_directory", directory)
        for writer, derived in (
            ("Write Diagnosis Request", "request_path"),
            ("Write Raw Diagnosis Response", "raw_response_path"),
            ("Write Diagnosis Result", "result_path"),
        ):
            written = nodes[writer]["parameters"]["fileName"]
            self.assertEqual(
                f"={{{{ $('{build_node}').first().json.{derived} }}}}", written
            )
            self.assertNotIn("$json.", written)

        provenance_code = nodes["Attach Diagnosis Provenance"]["parameters"]["jsCode"]
        self.assertIn("provider: context.provider", provenance_code)
        self.assertIn("model", provenance_code)
        self.assertIn("assertion_id", provenance_code)
        self.assertIn("parsed.assertion_id !== context.assertion_id", provenance_code)
        self.assertIn("transformation_defect", provenance_code)
        self.assertIn("test_defect", provenance_code)
        self.assertIn("ambiguous", provenance_code)
        self.assertNotIn("source.content", provenance_code)

        self.assertIn("diagnosis_request.json", build_code)
        self.assertIn("diagnosis_raw_response.txt", build_code)
        self.assertIn("diagnosis_result.json", build_code)

        request_code = build_code
        self.assertIn("/responses/source-diagnosis/", request_code)
        self.assertIn("messages", request_code)
        self.assertIn("system_prompt", request_code)
        self.assertIn("user_prompt", request_code)
        self.assertIn("assertion_id", request_code)
        self.assertIn("n8n-execution-", request_code)

        connections = document["connections"]
        self.assertEqual(
            "Call Diagnosis LLM",
            connections["Write Diagnosis Request"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Attach Diagnosis Provenance",
            connections["Write Raw Diagnosis Response"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Persist Diagnosis Artifact",
            connections["Write Diagnosis Result"]["main"][0][0]["node"],
        )

        return_code = nodes["Return Verdict"]["parameters"]["jsCode"]
        self.assertIn("assertion_id: verdict.assertion_id", return_code)

        master_path = WORKFLOWS_ROOT / "main" / "llm4mtl-agent-workflow.json"
        master = json.loads(master_path.read_text(encoding="utf-8"))
        master_nodes = {node["name"]: node for node in master["nodes"]}
        state_machine = master_nodes["State Machine"]["parameters"]["jsCode"]
        self.assertIn("assertion_id: verdict.assertion_id || null", state_machine)

        prompt_path = (
            REPOSITORY_ROOT
            / "prompt_assets"
            / "diagnosis"
            / "semantic_failure_diagnosis.md"
        )
        self.assertIn("assertion_id", prompt_path.read_text(encoding="utf-8"))

        persist = nodes["Persist Diagnosis Artifact"]
        self.assertEqual("n8n-nodes-base.httpRequest", persist["type"])
        self.assertIn("/runs/{{", persist["parameters"]["url"])
        self.assertIn("/diagnoses", persist["parameters"]["url"])

    def test_no_workflow_tree_keeps_its_own_copy_of_the_benchmark(self) -> None:
        """Task inputs live in benchmark/ only.

        Each n8n tree used to carry an ``mtl_snippets/`` copy of the reference
        transformations, mounted at ``/data/snippets``. Two copies of the same
        protected input is one copy too many: they drift, and a workflow reading
        the stale one produces results attributed to a reference that never ran.
        """
        self.assertEqual([], sorted(WORKFLOWS_ROOT.glob("*/mtl_snippets")))
        for compose in sorted(WORKFLOWS_ROOT.glob("*/docker-compose.yml")):
            with self.subTest(compose=compose):
                self.assertNotIn(
                    "/data/snippets",
                    compose.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
