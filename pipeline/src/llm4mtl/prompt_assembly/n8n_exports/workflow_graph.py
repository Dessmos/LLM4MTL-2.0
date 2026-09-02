"""Generic n8n workflow-graph mechanics, shared by every export.

Node and connection surgery that says nothing about what a workflow is for:
removing the cosmetic drift that blocks byte comparison between two languages'
exports, keeping only the provider node a workflow actually runs on, pinning
provider model ids and credential references, and renaming or removing
connection targets.

Nothing here knows what a model is asked — that is `prompts` — or which node
any particular export owns — that is `synchronizers`. These functions operate
on any n8n payload.
"""

from __future__ import annotations

import re
from typing import Any


TRIGGER_NODE = "When clicking 'Execute workflow'"

# Provider-side identifiers for the models the matrices name. Pinned here so a
# language cannot run a different build of "the same" model: QVT-O's Gemini
# exports asked for "models/gemini-2-5-pro", which is not a Google model id at
# all — those four runs would have failed rather than produced QVT-O results.
PROVIDER_MODEL_IDS = {
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini": "models/gemini-2.5-pro",
}

# One credential per provider, the one every other export already references.
# A chat model node carries the credential by id, and an id belongs to the n8n
# instance that stored it: the Reactions matrix kept three ids from a different
# instance, so its nodes failed with "Credential with ID ... does not exist" the
# moment the workflow finally reached them. Pinning the reference here keeps a
# node from pointing at a credential the pipeline's instance never had. Only the
# reference is pinned; the secret itself stays in n8n.
PROVIDER_CREDENTIALS = {
    "@n8n/n8n-nodes-langchain.lmChatOpenAi": (
        "openAiApi",
        {"id": "22X9yU5QaIUyA1Dx", "name": "OpenAi account"},
    ),
    "@n8n/n8n-nodes-langchain.lmChatAnthropic": (
        "anthropicApi",
        {"id": "R9d6pMqZ8LzipdDW", "name": "Anthropic account"},
    ),
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini": (
        "googlePalmApi",
        {"id": "nUZ88X2Akoz1dXpt", "name": "Google Gemini(PaLM) Api account"},
    ),
}


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
    """Remove per-workflow cosmetic drift that blocks byte comparison.

    Two things drifted per language rather than per purpose: the manual trigger
    was labelled with curly quotes in the ATL and Reactions exports and straight
    quotes elsewhere, and ATL's field assignments carried duplicate ids. Neither
    changes behaviour, but while they differ no one can diff two languages'
    workflows and see only the intended differences.

    The top-level workflow id is dropped for the same reason and one more: the
    master runs these exports as inline sub-workflows, and n8n files the
    sub-execution under ``workflow.id``.  A hand-written id that no
    ``workflow_entity`` row carries fails that insert on a foreign key, so the
    sub-workflow never starts.  Only the QVT-O transformation exports carried
    one, which is why QVT-O alone could not generate transformations.
    """
    payload.pop("id", None)
    for node in payload["nodes"]:
        _normalize_node_shape(payload, node)
    return _pin_provider_credentials(
        _pin_provider_model_ids(drop_unwired_chat_models(payload))
    )


def _normalize_node_shape(payload: dict[str, Any], node: dict[str, Any]) -> None:
    if node["type"] == "n8n-nodes-base.manualTrigger" and node["name"] != TRIGGER_NODE:
        payload["connections"] = rename_connection_node(
            payload["connections"],
            node["name"],
            TRIGGER_NODE,
        )
        node["name"] = TRIGGER_NODE
    normalize_node_entry_ids(node)


def normalize_node_entry_ids(node: dict[str, Any]) -> None:
    slug = re.sub(r"[^a-z0-9]+", "-", node["name"].lower()).strip("-")
    parameters = node.get("parameters", {})
    for holder in ("assignments", "conditions"):
        _normalize_parameter_entry_ids(parameters, holder, slug)


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
    """Keep only the provider node a workflow actually runs on.

    Model/strategy exports are produced by copying a sibling, so the ETL and ATL
    transformation workflows carried Anthropic and Gemini nodes with an empty
    ``ai_languageModel`` connection alongside the provider they use. They cannot
    execute, but they make a gpt-5 export look like it needs three credentials,
    and they are the reason two languages' exports could not be diffed.
    """
    connections = payload.get("connections", {})
    wired = _wired_chat_models(connections)
    payload["nodes"] = [
        node for node in payload["nodes"] if _keep_workflow_node(node, wired)
    ]
    live = {node["name"] for node in payload["nodes"]}
    for name in [name for name in connections if name not in live]:
        connections.pop(name)
    return payload


def _wired_chat_models(connections: dict[str, Any]) -> set[str]:
    return {
        name
        for name, outputs in connections.items()
        if any(targets for targets in outputs.get("ai_languageModel", []))
    }


def _keep_workflow_node(node: dict[str, Any], wired: set[str]) -> bool:
    if not node["type"].startswith("@n8n/n8n-nodes-langchain.lmChat"):
        return True
    return node["name"] in wired


def remove_connection_targets(
    value: Any,
    target_names: set[str],
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
