"""Synchronize n8n task-prompt and generation workflow exports.

The prompt-generation LLM receives one reference plus only the metamodels named
by that task's contract and produces a candidate natural-language task prompt.
After review, one frozen prompt per task is the common input to transformation
generation and semantic-test generation.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.conventions import LANGUAGE_CONFIGS, n8n_workflows_root
from llm4mtl.paths import TARGET

MODELS = (
    "gpt-5",
    "claude-sonnet-4",
    "gemini-2-5-pro",
    "qwen2-5-coder-7b",
)

# The prompting axis, spelled exactly as experiments/matrices/*.yaml spells it.
# Response directories are named after these, and a stage selects a run's
# responses by directory name — so a language that spells one of them
# differently (QVT-O's former "zero_shot" and "few_shot_AND_grammar") produces
# results no matrix can ever select.
STRATEGIES = (
    "only_prompt",
    "grammar",
    "few_shot",
    "few_shots_AND_grammar",
)
RESPONSE_IDENTITY = re.compile(r"/responses/([^/]+)/([^/]+)/")
READ_MODEL_FILES_NODE = "Read model files"
EXTRACT_MODEL_TEXT_NODE = "Extract text from model files"
READ_REFERENCE_FILE_NODE = "Read reference file"
SAVE_REACTION_NAME_NODE = "Save reaction name"
SAVE_FILE_NAME_NODE = "Save file name"
GENERATE_PROMPT_NODE = "Generate Prompt from Input"
WRITE_PROMPT_NODE = "Write prompt to disk"
READ_PROMPT_FILES_NODE = "Read prompt files"
GENERATE_CODE_NODE = "(Re-)Generate code"
MERGE_PROMPT_INPUTS_NODE = "Merge prompt and exact inputs"
LOOP_OVER_ITEMS_NODE = "Loop Over Items"
CONVERT_PROMPT_FILE_NODE = "Convert prompt to file"
READ_OUTPUT_CONTRACT_NODE = "Read output contract"
EXTRACT_CONTRACT_TEXT_NODE = "Extract text from contract"
ASSEMBLE_PROMPT_NODE = "Assemble prompt"
CONVERT_PROMPT_TO_FILE_NODE = "Convert prompt to File"


@dataclass(frozen=True)
class WorkflowInputs:
    display_name: str
    reference_extension: str
    # What "follow the grammar exactly" means in this language, and what its
    # named entities are called. These are the only parts of the transformation
    # instruction that may differ between languages; everything around them is
    # shared, so a model is asked for the same thing in every language.
    grammar_constructs: str
    named_entities: str
    extra_rule: str = ""


INPUTS = {
    "etl": WorkflowInputs(
        display_name="Epsilon Transformation Language (ETL)",
        reference_extension="etl",
        grammar_constructs=(
            "transformation rules with transform/to, @lazy/@greedy/@abstract/"
            "@primary annotations, guard conditions, pre/post blocks, "
            "operations, EOL expressions, equivalent operator ::=, etc."
        ),
        named_entities="transformation and rule",
    ),
    "atl": WorkflowInputs(
        display_name="ATLAS Transformation Language (ATL)",
        reference_extension="atl",
        grammar_constructs=(
            "module header, create section, matched/called rules, helpers, "
            "OCL expressions, etc."
        ),
        named_entities="module, transformation, and rule",
    ),
    "qvto": WorkflowInputs(
        display_name="QVT Operational (QVT-O)",
        reference_extension="qvto",
        grammar_constructs=(
            "modeltype declarations, transformation header with in/out "
            "parameters, main() entry point, mapping declarations with "
            "optional when clauses, init blocks, constructors, mapping "
            "extensions such as inherits/merges/disjuncts, resolve "
            "expressions, object literals, etc."
        ),
        named_entities="transformation and mapping",
    ),
    "reactions": WorkflowInputs(
        display_name="Vitruv Reactions Language",
        reference_extension="reactions",
        grammar_constructs=(
            "imports, transformation block, reactions, routines, guards, "
            "create/update sections, persistence paths, correspondence links, "
            "etc."
        ),
        named_entities="transformation, reaction, and routine",
        extra_rule=(
            "Use as much of the Reactions Language as possible and fall back "
            "to Xtend only where the language cannot express the change."
        ),
    ),
}

PROMPT_INPUT_NODE = "Resolve exact task inputs"
OBSOLETE_INPUT_NODES = {
    PROMPT_INPUT_NODE,
    "Extract text from reference file",
    READ_MODEL_FILES_NODE,
    EXTRACT_MODEL_TEXT_NODE,
    "Summarize",
    "Summarize models",
    "Read Grammar",
    "Extract text from grammar",
    "Merge models, reference and grammar",
}


def synchronize_prompt_generation(
    payload: dict[str, Any],
    language: str,
    model: str,
) -> dict[str, Any]:
    """Make prompt generation resolve exact inputs and write review candidates."""
    payload = _normalize_workflow_shape(payload)
    inputs = INPUTS[language]
    nodes = {node["name"]: node for node in payload["nodes"]}
    nodes[READ_REFERENCE_FILE_NODE]["parameters"]["fileSelector"] = (
        "=/data/benchmark/tasks/"
        f"{language}/references/*.{inputs.reference_extension}"
    )
    save_name = (
        SAVE_REACTION_NAME_NODE
        if SAVE_REACTION_NAME_NODE in nodes
        else SAVE_FILE_NAME_NODE
    )

    if GENERATE_PROMPT_NODE in nodes:
        generation = nodes[GENERATE_PROMPT_NODE]
        generation["parameters"]["text"] = _cloud_prompt_request(language)
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": _prompt_generation_system_message(language)}
        ]
        old_write_name = (
            "Write draft prompt to disk"
            if "Write draft prompt to disk" in nodes
            else WRITE_PROMPT_NODE
        )
        write_node = nodes[old_write_name]
        write_node["name"] = WRITE_PROMPT_NODE
        if old_write_name != WRITE_PROMPT_NODE:
            payload["connections"] = _rename_connection_node(
                payload["connections"],
                old_write_name,
                WRITE_PROMPT_NODE,
            )
    else:
        generation = nodes["Generate Prompt with local Qwen"]
        generation["parameters"]["jsonBody"] = _qwen_prompt_request(language)
        write_node = nodes[WRITE_PROMPT_NODE]
        payload["name"] = payload["name"].replace(
            "qwen2.5-coder-7b_smoke",
            "qwen2-5-coder-7b",
        )

    write_node["parameters"]["fileName"] = (
        "=/data/artifacts/task_prompt_candidates/"
        f'{language}/{model}/{{{{ $node["{save_name}"].json.baseName }}}}.txt'
    )
    payload["nodes"] = [
        node
        for node in payload["nodes"]
        if node["name"] not in OBSOLETE_INPUT_NODES
    ]
    payload["nodes"].append(_resolver_node(language, position=(-1376, 272)))
    payload["connections"] = _prompt_generation_connections(
        payload["connections"],
        trigger_name=next(
            node["name"]
            for node in payload["nodes"]
            if node["type"] == "n8n-nodes-base.manualTrigger"
        ),
        save_name=save_name,
        generation_name=generation["name"],
        is_qwen="Generate Prompt with local Qwen" == generation["name"],
    )
    return payload


def synchronize_test_generation(
    payload: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Make test generation consume the one frozen prompt for each task."""
    payload = _normalize_workflow_shape(payload)
    _response_identity(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    is_qwen = "Read Qwen prompt files" in nodes
    prompt_node_name = "Read Qwen prompt files" if is_qwen else READ_PROMPT_FILES_NODE
    nodes[prompt_node_name]["parameters"]["fileSelector"] = (
        f"=/data/task_prompts/{language}/*.txt"
    )
    _scope_helper_methods(nodes, language)

    if is_qwen:
        nodes["Save task name"]["parameters"]["assignments"]["assignments"][0][
            "value"
        ] = "={{$binary.data.fileName.replace(/\\.txt$/, '')}}"
        generation = nodes["Generate Test Suite with local Qwen"]
        generation["parameters"]["jsonBody"] = _qwen_test_request(language)
        payload["name"] = payload["name"].removesuffix("_smoke")
    else:
        generation = nodes["(Re-)Generate test suite"]
        # The assembled prompt is built in one Set node so that the exact text
        # sent to the model is a value that can be archived, not an expression
        # that only ever existed inside the generation node.
        generation["parameters"]["text"] = "={{ $json.assembled_prompt }}"
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": _test_generation_system_message(language)}
        ]
    merge_name = "Merge prompt, task and models" if is_qwen else "Merge"
    payload = _replace_language_wide_models(
        payload,
        language=language,
        save_name="Save task name" if is_qwen else SAVE_FILE_NAME_NODE,
        merge_name=merge_name,
        merge_input=2 if is_qwen else 1,
    )
    return _wire_output_contract(
        payload,
        language=language,
        merge_name=merge_name,
        merge_input=3 if is_qwen else 6,
        consumer=(
            "Generate Test Suite with local Qwen"
            if is_qwen
            else "(Re-)Generate test suite"
        ),
        is_qwen=is_qwen,
    )


def synchronize_transformation_generation(
    payload: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Make transformation generation use the shared prompt and exact models."""
    payload = _normalize_workflow_shape(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    if READ_PROMPT_FILES_NODE not in nodes or GENERATE_CODE_NODE not in nodes:
        raise ValueError("not a supported transformation-generation workflow")

    nodes[READ_PROMPT_FILES_NODE]["parameters"]["fileSelector"] = (
        f"=/data/task_prompts/{language}/*.txt"
    )
    _scope_helper_methods(nodes, language)
    generation = nodes[GENERATE_CODE_NODE]
    generation["parameters"]["text"] = _transformation_request()
    generation["parameters"].setdefault("messages", {})["messageValues"] = [
        {"message": _transformation_system_message(language)}
    ]
    save_name = (
        SAVE_FILE_NAME_NODE
        if SAVE_FILE_NAME_NODE in nodes
        else SAVE_REACTION_NAME_NODE
    )
    return _replace_language_wide_models(
        payload,
        language=language,
        save_name=save_name,
        merge_name="Merge",
        merge_input=1,
    )


def synchronize_reactions_matrix(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Use exact task inputs in the multi-model Reactions matrix workflow."""
    payload = _normalize_workflow_shape(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    nodes[READ_PROMPT_FILES_NODE]["parameters"]["fileSelector"] = (
        "=/data/task_prompts/reactions/*.txt"
    )
    _scope_helper_methods(nodes, "reactions")
    for generation_name in (
        "(Re-)Generate code1",
        "(Re-)Generate code3",
        "(Re-)Generate Code2",
    ):
        generation = nodes[generation_name]
        generation["parameters"]["text"] = _transformation_request()

    obsolete = {
        READ_MODEL_FILES_NODE,
        EXTRACT_MODEL_TEXT_NODE,
        "Summarize",
        PROMPT_INPUT_NODE,
        MERGE_PROMPT_INPUTS_NODE,
    }
    payload["nodes"] = [
        node for node in payload["nodes"] if node["name"] not in obsolete
    ]
    payload["nodes"].append(_resolver_node("reactions", position=(-448, 656)))
    payload["nodes"].append(
        {
            "parameters": {
                "mode": "combine",
                "combineBy": "combineByPosition",
                "numberInputs": 2,
                "options": {},
            },
            "id": "merge-prompt-and-exact-inputs-reactions",
            "name": MERGE_PROMPT_INPUTS_NODE,
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3.2,
            "position": [-176, 784],
        }
    )

    update_structure = nodes["Update-Structure"]["parameters"]["assignments"][
        "assignments"
    ]
    nodes["Update-Structure"]["parameters"]["assignments"]["assignments"] = [
        assignment
        for assignment in update_structure
        if assignment["name"] != "concatenated_model"
    ]
    nodes["Static-Files-Ready"]["parameters"]["numberInputs"] = 3

    connections = payload["connections"]
    for name in obsolete:
        connections.pop(name, None)
    _remove_connection_targets(connections, obsolete)

    trigger = connections[TRIGGER_NODE]["main"][0]
    trigger[:] = [
        target for target in trigger if target["node"] not in obsolete
    ]
    connections["Extract text from examples file"]["main"][0][0]["index"] = 0
    connections["Extract text from grammar"]["main"][0][0]["index"] = 1
    connections["Extract text from helper methods"]["main"][0][0]["index"] = 2

    connections[SAVE_REACTION_NAME_NODE] = {
        "main": [[
            {
                "node": "Extract text from prompt file",
                "type": "main",
                "index": 0,
            },
            {
                "node": PROMPT_INPUT_NODE,
                "type": "main",
                "index": 0,
            },
        ]]
    }
    connections["Extract text from prompt file"] = {
        "main": [[
            {
                "node": MERGE_PROMPT_INPUTS_NODE,
                "type": "main",
                "index": 0,
            }
        ]]
    }
    connections[PROMPT_INPUT_NODE] = {
        "main": [[
            {
                "node": MERGE_PROMPT_INPUTS_NODE,
                "type": "main",
                "index": 1,
            }
        ]]
    }
    connections[MERGE_PROMPT_INPUTS_NODE] = {
        "main": [[
            {"node": "If gpt-5", "type": "main", "index": 0},
            {"node": "If gemini-2.5-pro", "type": "main", "index": 0},
            {"node": "If claude-sonnet-4", "type": "main", "index": 0},
        ]]
    }
    return payload


def _resolver_node(
    language: str,
    *,
    position: tuple[int, int],
) -> dict[str, Any]:
    return {
        "parameters": {
            "method": "POST",
            "url": "http://stage-service:8129/prompt-inputs/resolve",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ { language: "
                f"'{language}', task: $json.baseName"
                " } }}"
            ),
            "options": {},
        },
        "id": f"resolve-exact-task-inputs-{language}",
        "name": PROMPT_INPUT_NODE,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": list(position),
    }


def _prompt_generation_connections(
    old_connections: dict[str, Any],
    *,
    trigger_name: str,
    save_name: str,
    generation_name: str,
    is_qwen: bool,
) -> dict[str, Any]:
    connections: dict[str, Any] = {
        trigger_name: {
            "main": [[{"node": READ_REFERENCE_FILE_NODE, "type": "main", "index": 0}]]
        },
        READ_REFERENCE_FILE_NODE: {
            "main": [[{"node": LOOP_OVER_ITEMS_NODE, "type": "main", "index": 0}]]
        },
        LOOP_OVER_ITEMS_NODE: {
            "main": [
                [],
                [
                    {
                        "node": save_name,
                        "type": "main",
                        "index": 0,
                    }
                ],
            ]
        },
        save_name: {
            "main": [[{"node": PROMPT_INPUT_NODE, "type": "main", "index": 0}]]
        },
        PROMPT_INPUT_NODE: {
            "main": [[{"node": generation_name, "type": "main", "index": 0}]]
        },
    }
    if is_qwen:
        connections[generation_name] = {
            "main": [[{"node": "Extract Qwen prompt text", "type": "main", "index": 0}]]
        }
        connections["Extract Qwen prompt text"] = {
            "main": [[{"node": CONVERT_PROMPT_FILE_NODE, "type": "main", "index": 0}]]
        }
    else:
        connections[generation_name] = {
            "main": [[{"node": CONVERT_PROMPT_FILE_NODE, "type": "main", "index": 0}]]
        }
        for source_name, source_connections in old_connections.items():
            language_model = source_connections.get("ai_languageModel")
            if language_model and _connection_targets(
                language_model,
                generation_name,
            ):
                connections[source_name] = {
                    "ai_languageModel": language_model
                }
    connections[CONVERT_PROMPT_FILE_NODE] = {
        "main": [[{"node": WRITE_PROMPT_NODE, "type": "main", "index": 0}]]
    }
    connections[WRITE_PROMPT_NODE] = {
        "main": [[{"node": LOOP_OVER_ITEMS_NODE, "type": "main", "index": 0}]]
    }
    return connections


TRIGGER_NODE = "When clicking 'Execute workflow'"

# Provider-side identifiers for the models the matrices name. Pinned here so a
# language cannot run a different build of "the same" model: QVT-O's Gemini
# exports asked for "models/gemini-2-5-pro", which is not a Google model id at
# all — those four runs would have failed rather than produced QVT-O results.
PROVIDER_MODEL_IDS = {
    "@n8n/n8n-nodes-langchain.lmChatGoogleGemini": "models/gemini-2.5-pro",
}


def _pin_provider_model_ids(payload: dict[str, Any]) -> dict[str, Any]:
    for node in payload["nodes"]:
        pinned = PROVIDER_MODEL_IDS.get(node.get("type", ""))
        if pinned is not None and node["parameters"].get("modelName") != pinned:
            node["parameters"]["modelName"] = pinned
    return payload


def _normalize_workflow_shape(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove per-workflow cosmetic drift that blocks byte comparison.

    Two things drifted per language rather than per purpose: the manual trigger
    was labelled with curly quotes in the ATL and Reactions exports and straight
    quotes elsewhere, and ATL's field assignments carried duplicate ids. Neither
    changes behaviour, but while they differ no one can diff two languages'
    workflows and see only the intended differences.
    """
    for node in payload["nodes"]:
        _normalize_node_shape(payload, node)
    return _pin_provider_model_ids(_drop_unwired_chat_models(payload))


def _normalize_node_shape(payload: dict[str, Any], node: dict[str, Any]) -> None:
    if node["type"] == "n8n-nodes-base.manualTrigger" and node["name"] != TRIGGER_NODE:
        payload["connections"] = _rename_connection_node(
            payload["connections"],
            node["name"],
            TRIGGER_NODE,
        )
        node["name"] = TRIGGER_NODE
    _normalize_node_entry_ids(node)


def _normalize_node_entry_ids(node: dict[str, Any]) -> None:
    slug = re.sub(r"[^a-z0-9]+", "-", node["name"].lower()).strip("-")
    parameters = node.get("parameters", {})
    for holder in ("assignments", "conditions"):
        entries = parameters.get(holder, {})
        entries = entries.get(holder) if isinstance(entries, dict) else None
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries, 1):
            if isinstance(entry, dict) and "id" in entry:
                entry["id"] = f"{slug}-{holder}-{index}"


def _drop_unwired_chat_models(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only the provider node a workflow actually runs on.

    Model/strategy exports are produced by copying a sibling, so the ETL and ATL
    transformation workflows carried Anthropic and Gemini nodes with an empty
    ``ai_languageModel`` connection alongside the provider they use. They cannot
    execute, but they make a gpt-5 export look like it needs three credentials,
    and they are the reason two languages' exports could not be diffed.
    """
    connections = payload.get("connections", {})
    wired = {
        name
        for name, outputs in connections.items()
        if any(targets for targets in outputs.get("ai_languageModel", []))
    }
    payload["nodes"] = [
        node
        for node in payload["nodes"]
        if not node["type"].startswith("@n8n/n8n-nodes-langchain.lmChat")
        or node["name"] in wired
    ]
    live = {node["name"] for node in payload["nodes"]}
    for name in [name for name in connections if name not in live]:
        connections.pop(name)
    return payload


def _transformation_system_message(language: str) -> str:
    """One instruction, one rule list, for every language.

    The four languages' instructions had drifted into four different texts:
    different rule numbering (ATL skipped rule 4), different punctuation, and a
    QVT-O display name used nowhere else. Only the grammar clause, the names of
    a language's declared entities, and one optional extra rule may differ.
    """
    inputs = INPUTS[language]
    rules = [
        f"Follow the {inputs.display_name} grammar exactly "
        f"({inputs.grammar_constructs}).",
        f"Use the {inputs.named_entities} names provided by the user whenever "
        "they are specified.",
        "If a name is missing, invent a concise, CamelCase name that matches "
        "the intent.",
        "Reference only the metamodel namespace URIs given in the request; do "
        "not invent, rename, or substitute a namespace.",
    ]
    if inputs.extra_rule:
        rules.append(inputs.extra_rule)
    rules.append(
        "Do **not** wrap the result in Markdown fences, and do **not** add "
        "commentary, explanations, or blank lines beyond what the language "
        "requires."
    )
    numbered = "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, 1))
    return (
        f"You are an expert developer for the **{inputs.display_name}** "
        "(model transformation DSL).\n"
        "Your job is to translate the user's natural-language specification "
        f"into a complete, syntactically valid .{inputs.reference_extension} "
        "file.\n\nRules\n"
        f"{numbered}"
    )


def _transformation_request() -> str:
    """The user turn. Identical in every language, including the namespaces.

    The namespace line used to be a hardcoded Vitruv URI in every workflow,
    which was simply untrue for ETL and ATL. It now comes from the contract.
    """
    return (
        "={{ $json.prompt }}\n\n"
        "-- End of request.\n"
        "Here are the authoritative metamodel files:\n"
        "{{ $json.metamodel_text }}\n\n"
        "The metamodel namespace URIs for this task are:\n"
        "{{ $json.metamodel_uri_text }}\n\n"
        "{{ $if($('Extract text from examples file').isExecuted, "
        '"Here are some examples as guideline:\\n" + '
        "$('Extract text from examples file').item.json.examples, \"\") }}\n\n"
        "{{ $if($('Extract text from grammar').isExecuted, "
        '"Here is the grammar of the Language:\\n" + '
        "$('Extract text from grammar').item.json.grammar, \"\") }}\n\n"
        "{{ $if($('Extract text from helper methods').isExecuted, "
        '"Here are helper methods you can use:\\n" + '
        "$('Extract text from helper methods').item.json.helper_methods, \"\") }}"
    )


def _scope_helper_methods(nodes: dict[str, Any], language: str) -> None:
    """Read helper methods from this language's directory, like every other asset.

    Every workflow but one used ``/data/helper_methods//*``, which globs the
    language directories themselves rather than the files inside them — and on
    the test-generation instance the volume was not even mounted. Few-shot
    examples and grammars have always been language-scoped; helper methods now
    are too.
    """
    node = nodes.get("Read helper methods")
    if node is None:
        return
    node["parameters"]["fileSelector"] = f"=/data/helper_methods/{language}/*"


def _replace_language_wide_models(
    payload: dict[str, Any],
    *,
    language: str,
    save_name: str,
    merge_name: str,
    merge_input: int,
) -> dict[str, Any]:
    obsolete = {
        READ_MODEL_FILES_NODE,
        EXTRACT_MODEL_TEXT_NODE,
        "Summarize",
        "Summarize models",
    }
    payload["nodes"] = [
        node for node in payload["nodes"] if node["name"] not in obsolete
    ]
    payload["nodes"] = [
        node for node in payload["nodes"] if node["name"] != PROMPT_INPUT_NODE
    ]
    payload["nodes"].append(_resolver_node(language, position=(736, -368)))

    connections = payload["connections"]
    for name in obsolete:
        connections.pop(name, None)
    _remove_connection_targets(connections, obsolete | {PROMPT_INPUT_NODE})
    save_connections = connections.setdefault(save_name, {}).setdefault(
        "main",
        [[]],
    )
    if not save_connections:
        save_connections.append([])
    save_connections[0].append(
        {"node": PROMPT_INPUT_NODE, "type": "main", "index": 0}
    )
    connections[PROMPT_INPUT_NODE] = {
        "main": [[{"node": merge_name, "type": "main", "index": merge_input}]]
    }
    node_names = {node["name"] for node in payload["nodes"]}
    for source_name in tuple(connections):
        if source_name not in node_names:
            connections.pop(source_name)
    return payload


CONTRACT_NODES = (
    READ_OUTPUT_CONTRACT_NODE,
    EXTRACT_CONTRACT_TEXT_NODE,
    ASSEMBLE_PROMPT_NODE,
    CONVERT_PROMPT_TO_FILE_NODE,
    WRITE_PROMPT_NODE,
)


def _wire_output_contract(
    payload: dict[str, Any],
    *,
    language: str,
    merge_name: str,
    merge_input: int,
    consumer: str,
    is_qwen: bool,
) -> dict[str, Any]:
    """Deliver the output contract on every strategy and archive the prompt.

    The contract used to live inside the few-shot examples file, so only the
    ``few_shot`` and ``few_shots_AND_grammar`` variants ever received it: the
    other two asked for a structured artifact without ever stating its shape.
    It is not a prompting treatment, so it hangs off the loop directly and the
    ``Few_shot`` switch no longer decides whether the model is told what to
    emit. The strategy axis now varies examples alone.

    The assembled prompt is written next to the response it produced, because a
    response that violates the contract is otherwise indistinguishable from a
    prompt that never carried it.
    """
    nodes = {node["name"]: node for node in payload["nodes"]}
    response_path = nodes["Write response to disk"]["parameters"]["fileName"]
    if "/responses/" not in response_path:
        raise ValueError("cannot derive the prompt archive path")

    payload["nodes"] = [
        node for node in payload["nodes"] if node["name"] not in CONTRACT_NODES
    ]
    connections = payload["connections"]
    for name in CONTRACT_NODES:
        connections.pop(name, None)
    _remove_connection_targets(connections, set(CONTRACT_NODES))

    payload["nodes"] += _output_contract_nodes(
        language,
        response_path,
        is_qwen,
    )

    connections[LOOP_OVER_ITEMS_NODE]["main"][1].append(
        {"node": READ_OUTPUT_CONTRACT_NODE, "type": "main", "index": 0}
    )
    connections[READ_OUTPUT_CONTRACT_NODE] = {
        "main": [[
            {"node": EXTRACT_CONTRACT_TEXT_NODE, "type": "main", "index": 0}
        ]]
    }
    connections[EXTRACT_CONTRACT_TEXT_NODE] = {
        "main": [[
            {"node": merge_name, "type": "main", "index": merge_input}
        ]]
    }
    connections[merge_name] = {
        "main": [[{"node": ASSEMBLE_PROMPT_NODE, "type": "main", "index": 0}]]
    }
    connections[ASSEMBLE_PROMPT_NODE] = {
        "main": [[
            {"node": consumer, "type": "main", "index": 0},
            {"node": CONVERT_PROMPT_TO_FILE_NODE, "type": "main", "index": 0},
        ]]
    }
    connections[CONVERT_PROMPT_TO_FILE_NODE] = {
        "main": [[
            {"node": WRITE_PROMPT_NODE, "type": "main", "index": 0}
        ]]
    }
    for node in payload["nodes"]:
        if node["name"] == merge_name:
            node["parameters"]["numberInputs"] = merge_input + 1
    return payload


def _output_contract_nodes(
    language: str,
    response_path: str,
    is_qwen: bool,
) -> list[dict[str, Any]]:
    offset = 0 if is_qwen else 1
    return [
        {
            "parameters": {
                "fileSelector": (
                    f"=/data/contract/{language}/semantic_cases_contract.txt"
                ),
                "options": {},
            },
            "id": f"read-output-contract-{language}",
            "name": READ_OUTPUT_CONTRACT_NODE,
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [448 if offset else -512, -160 if offset else 96],
        },
        {
            "parameters": {
                "operation": "text",
                "destinationKey": "output_contract",
                "options": {},
            },
            "id": f"extract-text-from-contract-{language}",
            "name": EXTRACT_CONTRACT_TEXT_NODE,
            "type": "n8n-nodes-base.extractFromFile",
            "typeVersion": 1,
            "position": [736 if offset else -288, -160 if offset else 96],
        },
        {
            "parameters": {
                "assignments": {
                    "assignments": [
                        {
                            "id": "assemble-prompt-assignments-1",
                            "name": "assembled_prompt",
                            "value": (
                                _qwen_assembled_prompt()
                                if is_qwen
                                else _cloud_test_request(language)
                            ),
                            "type": "string",
                        }
                    ]
                },
                "includeOtherFields": True,
                "options": {},
            },
            "id": "assemble-prompt",
            "name": ASSEMBLE_PROMPT_NODE,
            "type": "n8n-nodes-base.set",
            "typeVersion": 3.4,
            "position": [1232 if offset else 208, -288],
        },
        {
            "parameters": {
                "operation": "toText",
                "sourceProperty": "assembled_prompt",
                "binaryPropertyName": "data",
                "options": {},
            },
            "id": "convert-prompt-to-file",
            "name": CONVERT_PROMPT_TO_FILE_NODE,
            "type": "n8n-nodes-base.convertToFile",
            "typeVersion": 1.1,
            "position": [1440 if offset else 432, -448],
        },
        {
            "parameters": {
                "operation": "write",
                "fileName": response_path.replace("/responses/", "/prompts/", 1),
                "dataPropertyName": "data",
                "options": {},
            },
            "id": "write-prompt-to-disk",
            "name": WRITE_PROMPT_NODE,
            "type": "n8n-nodes-base.readWriteFile",
            "typeVersion": 1,
            "position": [1632 if offset else 656, -448],
        },
    ]


def _remove_connection_targets(
    value: Any,
    target_names: set[str],
) -> None:
    if isinstance(value, dict):
        for nested in value.values():
            _remove_connection_targets(nested, target_names)
        return
    if not isinstance(value, list):
        return
    value[:] = [
        nested
        for nested in value
        if not (
            isinstance(nested, dict)
            and nested.get("node") in target_names
        )
    ]
    for nested in value:
        _remove_connection_targets(nested, target_names)


def _connection_targets(value: Any, target_name: str) -> bool:
    if isinstance(value, dict):
        if value.get("node") == target_name:
            return True
        return any(
            _connection_targets(nested, target_name)
            for nested in value.values()
        )
    if isinstance(value, list):
        return any(
            _connection_targets(nested, target_name)
            for nested in value
        )
    return False


def _cloud_prompt_request(language: str) -> str:
    inputs = INPUTS[language]
    special = _prompt_language_requirements(language)
    return (
        f"=Task name: {{{{ $json.task }}}}\n\n"
        "Reference transformation (authoritative):\n"
        "File: {{ $json.reference.path }}\n"
        "{{ $json.reference.content }}\n\n"
        "Exact task-specific metamodel files selected by the task contract:\n"
        "{{ $json.metamodel_text || '(no external metamodel file is required by the task contract)' }}\n\n"
        f"{inputs.display_name} grammar:\n{{{{ $json.grammar.content }}}}\n\n"
        "Reconstruct the concise natural-language developer request that could "
        "have produced this reference transformation. Preserve the task's "
        "observable intent and explicitly name its transformation rules, "
        "mappings, or reactions. Do not generate code or tests. Do not add facts "
        "that are absent from these inputs. Keep the request under 100 words.\n\n"
        f"{special}\n\nReturn only the task prompt text."
    )


def _prompt_generation_system_message(language: str) -> str:
    return (
        "You reconstruct one reusable natural-language task prompt for "
        f"{INPUTS[language].display_name}. The same reviewed prompt will be used "
        "for transformation generation and semantic-test generation. Use only "
        "the current reference, its task-contract-selected metamodels, the "
        "grammar, and the task name. Do not generate either artifact here."
    )


def _qwen_prompt_request(language: str) -> str:
    system = json.dumps(
        _prompt_generation_system_message(language),
        ensure_ascii=False,
    )
    requirements = json.dumps(_prompt_language_requirements(language), ensure_ascii=False)
    return (
        "={{ JSON.stringify({ model: 'qwen2.5-coder:7b', stream: false, "
        f"messages: [{{ role: 'system', content: {system} }}, "
        "{ role: 'user', content: "
        "'Task name: ' + ($json.task || '') + "
        "'\\n\\nReference transformation (' + ($json.reference.path || '') + '):\\n' + "
        "($json.reference.content || '') + "
        "'\\n\\nExact task-specific metamodel files:\\n' + "
        "($json.metamodel_text || '(no external metamodel file is required by the task contract)') + "
        "'\\n\\nGrammar:\\n' + (($json.grammar || {}).content || '') + "
        "'\\n\\nReconstruct the concise natural-language developer request that "
        "could have produced this reference. Preserve observable intent and "
        "explicitly name its rules, mappings, or reactions. Do not generate code "
        "or tests, do not invent facts, and keep it under 100 words. "
        f"Language-specific requirements: ' + {requirements} + "
        "'\\n\\nReturn only the task prompt text.' }], "
        "options: { temperature: 0.1, top_p: 1 } }) }}"
    )


# The frozen task prompt describes the transformation under test. It is written
# for the transformation generator, so test generation has to say out loud what
# role it plays here, or the model answers it instead of testing it.
TASK_SPECIFICATION_HEADER = (
    "## Task specification (describes the transformation under test: "
    "write tests for it, do not implement it)\\n"
)
CONTRACT_SECTION_HEADER = (
    "\\n\\n## REQUIRED OUTPUT CONTRACT "
    "(binding, overrides every other section)\\n"
)
FEW_SHOT_SECTION_HEADER = (
    "\\n\\n## Few-shot examples (they illustrate the binding contract above; "
    "on any conflict the contract wins)\\n"
)


def _cloud_test_request(language: str) -> str:
    grammar_name = INPUTS[language].display_name
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + $json.prompt + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.output_contract || "") + '
        '$if($("Extract text from examples file").isExecuted, '
        f'"{FEW_SHOT_SECTION_HEADER}" + '
        '$("Extract text from examples file").item.json.examples, "") + '
        '$if($("Extract text from grammar").isExecuted, '
        f'"\\n\\n## {grammar_name} grammar (syntax guidance only)\\n" + '
        '$("Extract text from grammar").item.json.grammar, "") + '
        '$if($("Extract text from helper methods").isExecuted, '
        '"\\n\\n## Existing helper methods (background only)\\n" + '
        '$("Extract text from helper methods").item.json.helper_methods, "") }}'
    )


def _qwen_assembled_prompt() -> str:
    """The local-Qwen variant has no examples, grammar, or helper sections."""
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + ($json.prompt || "") + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.output_contract || "") }}}}'
    )


def _test_generation_system_message(language: str) -> str:
    """Defer to the contract instead of paraphrasing it.

    This message used to restate the artifact shape in its own words, and the
    two texts disagreed. It listed the model fields as "name, kind, role, path,
    generated, and metamodelUri only for EMF", which reads as the literal value
    ``"EMF"``; it named neither the closed ``kind``/``role`` vocabularies nor
    the mandatory ``model`` and ``type`` fields of an assertion. Being the
    highest-priority instruction, it won over the contract that stated all of
    them, and every generated ATL suite reproduced this message rather than the
    contract. One authority now states the shape, and this message points at it.
    """
    message = (
        f"Generate semantic test artifacts for {INPUTS[language].display_name} "
        "from the reviewed shared task prompt. The task specification describes "
        "the transformation under test: write tests for it, do not implement "
        "it. Use the exact task-specific metamodel files.\n\n"
        "The user message contains a section titled REQUIRED OUTPUT CONTRACT. "
        "That section is binding and complete: it lists every allowed field "
        "name and every allowed field value of semantic_cases.json. Follow it "
        "literally. Do not introduce a field name or a field value that it does "
        "not list, and do not substitute a synonym for one that it does list. "
        "Where any other section of the prompt appears to disagree with it, the "
        "contract wins.\n\n"
        "Return only fenced file blocks: exactly one "
        "```json file=semantic_cases.json block and the model file blocks that "
        "it references. Never generate Java, JUnit, transformation code, Maven "
        "files, helper classes, or prose outside file blocks."
    )
    if language == "reactions":
        message += (
            ' Every test must use scenarioKind "change_propagation", model role '
            '"inout", and the closed declarative tests[].changes vocabulary. '
            "Do not reinterpret Reactions as a batch source-to-target transform."
        )
    return message


def _qwen_test_request(language: str) -> str:
    system = json.dumps(
        _test_generation_system_message(language),
        ensure_ascii=False,
    )
    return (
        "={{ JSON.stringify({ model: 'qwen2.5-coder:7b', stream: false, "
        f"messages: [{{ role: 'system', content: {system} }}, "
        "{ role: 'user', content: ($json.assembled_prompt || '') }], "
        "options: { temperature: 0.1, top_p: 1 } }) }}"
    )


def _prompt_language_requirements(language: str) -> str:
    if language == "reactions":
        return (
            "Describe the reaction-triggered change and its propagated effect; "
            "do not reinterpret it as a source-to-target batch transformation."
        )
    return (
        "Describe the source-to-target transformation intent at a high level "
        "without metamodel-qualified type prefixes."
    )


def _response_identity(payload: dict[str, Any]) -> tuple[str, str]:
    write_node = next(
        node for node in payload["nodes"] if node["name"] == "Write response to disk"
    )
    match = RESPONSE_IDENTITY.search(write_node["parameters"]["fileName"])
    if match is None:
        raise ValueError("cannot infer model and strategy from response path")
    return match.group(1), match.group(2)


def _model_from_filename(path: Path) -> str:
    for model in MODELS:
        if model in path.name:
            return model
    raise ValueError(f"cannot infer model from {path}")


def _rename_connection_node(value: Any, old_name: str, new_name: str) -> Any:
    if isinstance(value, list):
        return [
            _rename_connection_node(item, old_name, new_name)
            for item in value
        ]
    if isinstance(value, dict):
        renamed: dict[str, Any] = {}
        for key, nested in value.items():
            renamed_key = new_name if key == old_name else key
            renamed[renamed_key] = _rename_connection_node(
                nested,
                old_name,
                new_name,
            )
        if renamed.get("node") == old_name:
            renamed["node"] = new_name
        return renamed
    return value


def synchronize_exports() -> tuple[int, int, int]:
    prompt_count = 0
    test_count = 0
    for language, config in sorted(LANGUAGE_CONFIGS.items()):
        root = n8n_workflows_root(config)
        language_prompt_count, language_test_count = _synchronize_test_workflows(
            root,
            language,
        )
        prompt_count += language_prompt_count
        test_count += language_test_count

    transformation_root = TARGET.workflows / "transformations" / "workflows"
    prompt_count += _synchronize_transformation_prompt_workflows(
        transformation_root
    )
    transformation_count = _synchronize_transformation_workflows(
        transformation_root
    )
    transformation_count += _synchronize_reactions_matrix(transformation_root)
    return prompt_count, test_count, transformation_count


def _synchronize_test_workflows(root: Path, language: str) -> tuple[int, int]:
    prompt_count = 0
    for path in sorted((root / "prompt_generation").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _write_json(
            path,
            synchronize_prompt_generation(
                payload,
                language,
                _model_from_filename(path),
            ),
        )
        prompt_count += 1

    test_count = 0
    for path in sorted((root / "test_generation").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        _write_json(
            path,
            synchronize_test_generation(payload, language),
        )
        test_count += 1
    return prompt_count, test_count


def _synchronize_transformation_prompt_workflows(
    transformation_root: Path,
) -> int:
    prompt_count = 0
    for path in sorted(transformation_root.rglob("Prompt_generation*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        node_names = {node.get("name") for node in payload.get("nodes", [])}
        if GENERATE_PROMPT_NODE not in node_names:
            continue
        language = _language_from_workflow_path(path)
        _write_json(
            path,
            synchronize_prompt_generation(
                payload,
                language,
                "gpt-5-chat-latest",
            ),
        )
        prompt_count += 1
    return prompt_count


def _synchronize_transformation_workflows(transformation_root: Path) -> int:
    transformation_count = 0
    for path in sorted(transformation_root.rglob("Prompting*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        node_names = {node.get("name") for node in payload.get("nodes", [])}
        if GENERATE_CODE_NODE not in node_names:
            continue
        language = _transformation_language(payload)
        _write_json(
            path,
            synchronize_transformation_generation(payload, language),
        )
        transformation_count += 1
    return transformation_count


def _synchronize_reactions_matrix(transformation_root: Path) -> int:
    reactions_matrix = (
        transformation_root
        / "updated_reactions_workflow"
        / "generate_reactions"
        / "LLM4MTL_Generate_Reactions_for_all_Configurations.json"
    )
    if reactions_matrix.is_file():
        payload = json.loads(reactions_matrix.read_text(encoding="utf-8"))
        _write_json(
            reactions_matrix,
            synchronize_reactions_matrix(payload),
        )
        return 1
    return 0


def _language_from_workflow_path(path: Path) -> str:
    value = path.as_posix().lower()
    if "qvto" in value:
        return "qvto"
    if "reactions" in value:
        return "reactions"
    if "atl" in value:
        return "atl"
    if "etl" in value:
        return "etl"
    raise ValueError(f"cannot infer workflow language from {path}")


def _transformation_language(payload: dict[str, Any]) -> str:
    nodes = {node["name"]: node for node in payload["nodes"]}
    selector = nodes[READ_PROMPT_FILES_NODE]["parameters"]["fileSelector"]
    match = re.search(
        r"/(?:transformation_generation|task_prompts)/(etl|atl|qvto|reactions)/",
        selector,
    )
    if match is None:
        raise ValueError("cannot infer transformation workflow language")
    return match.group(1)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize shared task-prompt, transformation-generation, and "
            "semantic-test-generation n8n exports."
        )
    )
    parser.add_argument("--write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.write:
        raise SystemExit("pass --write to update workflow exports")
    prompt_count, test_count, transformation_count = synchronize_exports()
    print(
        f"synchronized {prompt_count} prompt-generation and "
        f"{test_count} test-generation workflows and "
        f"{transformation_count} transformation-generation workflows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
