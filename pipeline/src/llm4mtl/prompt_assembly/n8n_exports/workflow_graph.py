"""Generic n8n workflow-graph mechanics, shared by every export.

Node and connection edits that work on any n8n payload: removing cosmetic
differences between exports, keeping only the chat model node that is wired,
pinning provider model ids and credential references, building nodes and
connections, and renaming or removing nodes and edges.

What a model is asked lives in `prompts`; which nodes a given export has lives
in `synchronizers`.
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any


TRIGGER_NODE = "When clicking 'Execute workflow'"
MANUAL_TRIGGER_TYPE = "n8n-nodes-base.manualTrigger"
CHAT_MODEL_TYPE_PREFIX = "@n8n/n8n-nodes-langchain.lmChat"
OPENAI_CHAT_MODEL_TYPE = CHAT_MODEL_TYPE_PREFIX + "OpenAi"
ANTHROPIC_CHAT_MODEL_TYPE = CHAT_MODEL_TYPE_PREFIX + "Anthropic"
GEMINI_CHAT_MODEL_TYPE = CHAT_MODEL_TYPE_PREFIX + "GoogleGemini"


@dataclass(frozen=True)
class NodeType:
    """An n8n node type and the type version that new nodes of it get."""

    name: str
    version: int | float


HTTP_REQUEST = NodeType("n8n-nodes-base.httpRequest", 4.2)
MERGE = NodeType("n8n-nodes-base.merge", 3.2)
READ_WRITE_FILE = NodeType("n8n-nodes-base.readWriteFile", 1)
EXTRACT_FROM_FILE = NodeType("n8n-nodes-base.extractFromFile", 1)
SET = NodeType("n8n-nodes-base.set", 3.4)
CONVERT_TO_FILE = NodeType("n8n-nodes-base.convertToFile", 1.1)

_NON_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")

# Provider-side model ids, pinned so every language runs the same model build.
# A wrong id (for example "models/gemini-2-5-pro") makes the run fail.
PROVIDER_MODEL_IDS = {
    GEMINI_CHAT_MODEL_TYPE: "models/gemini-2.5-pro",
}

# One credential reference per provider. A chat model node names its credential
# by id, and an id is valid only in the n8n instance that stored it; an id from
# another instance fails with "Credential with ID ... does not exist". Only the
# reference is pinned here; the secret stays in n8n.
PROVIDER_CREDENTIALS = {
    OPENAI_CHAT_MODEL_TYPE: (
        "openAiApi",
        {"id": "22X9yU5QaIUyA1Dx", "name": "OpenAi account"},
    ),
    ANTHROPIC_CHAT_MODEL_TYPE: (
        "anthropicApi",
        {"id": "R9d6pMqZ8LzipdDW", "name": "Anthropic account"},
    ),
    GEMINI_CHAT_MODEL_TYPE: (
        "googlePalmApi",
        {"id": "nUZ88X2Akoz1dXpt", "name": "Google Gemini(PaLM) Api account"},
    ),
}


# Every prompt asset is UTF-8. A text extraction that names no encoding makes
# n8n guess one per file, and the guess turns a short UTF-8 task prompt with a
# typographic apostrophe into windows-1252 mojibake ("Node’s" -> "Nodeâ€™s")
# before it reaches the model.
TEXT_EXTRACTION_ENCODING = "utf8"


def _pin_text_extraction_encoding(payload: dict[str, Any]) -> dict[str, Any]:
    for node in payload["nodes"]:
        if node.get("type") != EXTRACT_FROM_FILE.name:
            continue
        if node["parameters"].get("operation") != "text":
            continue
        node["parameters"].setdefault("options", {})["encoding"] = TEXT_EXTRACTION_ENCODING
    return payload


def _pin_provider_model_ids(payload: dict[str, Any]) -> dict[str, Any]:
    for node in payload["nodes"]:
        pinned = PROVIDER_MODEL_IDS.get(node.get("type", ""))
        if pinned is not None and node["parameters"].get("modelName") != pinned:
            node["parameters"]["modelName"] = pinned
    return payload


def _pin_provider_credentials(payload: dict[str, Any]) -> dict[str, Any]:
    for node in payload["nodes"]:
        pinned = PROVIDER_CREDENTIALS.get(node.get("type", ""))
        if pinned is None or "credentials" not in node:
            continue
        credential_type, reference = pinned
        node["credentials"][credential_type] = dict(reference)
    return payload


def normalize_workflow_shape(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove cosmetic differences, so two languages' exports diff cleanly.

    Gives the manual trigger one fixed name and renumbers assignment and
    condition ids. Also drops unwired chat models and pins provider model ids,
    credentials, and the encoding every text extraction decodes with.

    The top-level workflow ``id`` is removed too. The master workflow runs these
    exports as inline sub-workflows, and n8n stores each sub-execution under
    ``workflow.id``. An id with no ``workflow_entity`` row fails that insert on
    a foreign key, and the sub-workflow never starts.
    """
    payload.pop("id", None)
    for node in payload["nodes"]:
        _normalize_node_shape(payload, node)
    return _pin_text_extraction_encoding(
        _pin_provider_credentials(
            _pin_provider_model_ids(drop_unwired_chat_models(payload))
        )
    )


def _normalize_node_shape(payload: dict[str, Any], node: dict[str, Any]) -> None:
    if node["type"] == MANUAL_TRIGGER_TYPE and node["name"] != TRIGGER_NODE:
        payload["connections"] = rename_connection_node(
            payload["connections"],
            node["name"],
            TRIGGER_NODE,
        )
        node["name"] = TRIGGER_NODE
    normalize_node_entry_ids(node)


def normalize_node_entry_ids(node: dict[str, Any]) -> None:
    slug = node_slug(node["name"])
    parameters = node.get("parameters", {})
    for holder in ("assignments", "conditions"):
        _normalize_parameter_entry_ids(parameters, holder, slug)


def node_slug(name: str) -> str:
    """A node name in lower case, with each run of other characters as one dash."""
    return _NON_SLUG_CHARACTERS.sub("-", name.lower()).strip("-")


def _normalize_parameter_entry_ids(
    parameters: dict[str, Any],
    holder: str,
    slug: str,
) -> None:
    entries = parameters.get(holder, {})
    entries = entries.get(holder) if isinstance(entries, dict) else None
    if not isinstance(entries, list):
        return
    for index, entry in enumerate(entries, 1):
        if isinstance(entry, dict) and "id" in entry:
            entry["id"] = f"{slug}-{holder}-{index}"


def drop_unwired_chat_models(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove chat model nodes that have no ``ai_languageModel`` connection.

    Exports copied from a sibling can keep other providers' chat model nodes.
    They never run, but they make a workflow look like it needs more
    credentials, and they add noise when diffing exports.
    """
    wired = _wired_chat_models(payload.get("connections", {}))
    payload["nodes"] = [
        node for node in payload["nodes"] if _keep_workflow_node(node, wired)
    ]
    drop_dangling_sources(payload)
    return payload


def drop_dangling_sources(payload: dict[str, Any]) -> None:
    """Remove the outgoing connections of nodes that no longer exist."""
    connections = payload.get("connections", {})
    live = {node["name"] for node in payload["nodes"]}
    for name in [name for name in connections if name not in live]:
        connections.pop(name)


def _wired_chat_models(connections: dict[str, Any]) -> set[str]:
    return {
        name
        for name, outputs in connections.items()
        if any(targets for targets in outputs.get("ai_languageModel", []))
    }


def _keep_workflow_node(node: dict[str, Any], wired: set[str]) -> bool:
    if not node["type"].startswith(CHAT_MODEL_TYPE_PREFIX):
        return True
    return node["name"] in wired


def new_node(
    node_type: NodeType,
    *,
    name: str,
    node_id: str,
    position: tuple[int, int],
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """A node in the key order that n8n exports use."""
    return {
        "parameters": parameters,
        "id": node_id,
        "name": name,
        "type": node_type.name,
        "typeVersion": node_type.version,
        "position": list(position),
    }


def main_edge(target: str, input_index: int = 0) -> dict[str, Any]:
    """A "main" connection into input ``input_index`` of node ``target``."""
    return {"node": target, "type": "main", "index": input_index}


def main_output(*edges: dict[str, Any]) -> dict[str, Any]:
    """The connections of a node with one "main" output that feeds ``edges``."""
    return {"main": [list(edges)]}


def connect_in_sequence(*names: str) -> dict[str, Any]:
    """Connections that feed each named node into the next one."""
    return {
        source: main_output(main_edge(target))
        for source, target in zip(names, names[1:])
    }


def remove_nodes(payload: dict[str, Any], names: Collection[str]) -> None:
    """Delete the named nodes, their outgoing connections, and every edge into them."""
    payload["nodes"] = [node for node in payload["nodes"] if node["name"] not in names]
    connections = payload["connections"]
    for name in names:
        connections.pop(name, None)
    remove_connection_targets(connections, names)


def remove_connection_targets(
    value: Any,
    target_names: Collection[str],
) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            remove_connection_targets(nested, target_names)
        return
    if not isinstance(value, list):
        return
    value[:] = [
        nested
        for nested in value
        if not (isinstance(nested, dict) and nested.get("node") in target_names)
    ]
    for nested in value:
        remove_connection_targets(nested, target_names)


def connection_targets(value: Any, target_name: str) -> bool:
    if isinstance(value, dict):
        if value.get("node") == target_name:
            return True
        return any(connection_targets(nested, target_name) for nested in value.values())
    if isinstance(value, list):
        return any(connection_targets(nested, target_name) for nested in value)
    return False


def rename_connection_node(value: Any, old_name: str, new_name: str) -> Any:
    if isinstance(value, list):
        return [rename_connection_node(item, old_name, new_name) for item in value]
    if isinstance(value, dict):
        return _rename_connection_mapping(value, old_name, new_name)
    return value


def _rename_connection_mapping(
    value: dict[str, Any],
    old_name: str,
    new_name: str,
) -> dict[str, Any]:
    renamed: dict[str, Any] = {}
    for key, nested in value.items():
        renamed_key = new_name if key == old_name else key
        renamed[renamed_key] = rename_connection_node(
            nested,
            old_name,
            new_name,
        )
    if renamed.get("node") == old_name:
        renamed["node"] = new_name
    return renamed
