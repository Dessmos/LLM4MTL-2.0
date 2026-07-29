from __future__ import annotations

import json
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
                        parameters.get("fileName", "").startswith("=/data/artifacts/"),
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

        provenance_code = nodes["Attach Diagnosis Provenance"]["parameters"]["jsCode"]
        self.assertIn("provider: context.provider", provenance_code)
        self.assertIn("model", provenance_code)

        persist = nodes["Persist Diagnosis Artifact"]
        self.assertEqual("n8n-nodes-base.httpRequest", persist["type"])
        self.assertIn("/runs/{{ $json.run_id }}/diagnoses", persist["parameters"]["url"])

    def test_snippets_contains_only_immutable_inputs(self) -> None:
        for snippets_root in WORKFLOWS_ROOT.glob("*/mtl_snippets"):
            for path in snippets_root.rglob("*"):
                if not path.is_file():
                    continue
                relative_parts = path.relative_to(snippets_root).parts
                self.assertTrue(
                    "references" in relative_parts or "task_contracts" in relative_parts,
                    f"generated or unclassified file remains in snippets: {path}",
                )


if __name__ == "__main__":
    unittest.main()
