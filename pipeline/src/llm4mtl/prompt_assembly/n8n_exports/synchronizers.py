"""What each n8n export is rewritten to do, workflow by workflow.

One synchronizer per generation workflow. Each takes an exported payload,
rewrites the nodes and connections that must not differ between languages, and
returns the payload to be written back. The text it installs comes from
`prompts`; the node and connection mechanics it uses come from
`workflow_graph`.

These functions are the record of every deliberate difference between the four
languages' workflows. Anything a synchronizer does not rewrite is drift, and
the reason each rewrite exists is stated where it happens.
"""

from __future__ import annotations

import json
import re
from typing import Any

from llm4mtl.prompt_assembly.n8n_exports.prompts import (
    INPUTS,
    cloud_prompt_request,
    cloud_test_request,
    prompt_generation_system_message,
    qwen_assembled_prompt,
    qwen_prompt_request,
    qwen_test_request,
    test_generation_system_message,
    transformation_request,
    transformation_system_message,
)
from llm4mtl.prompt_assembly.n8n_exports.workflow_graph import (
    TRIGGER_NODE,
    connection_targets,
    normalize_workflow_shape,
    remove_connection_targets,
    rename_connection_node,
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


# Tried in order; the first condition that matches the run's model wins.
REACTIONS_MODEL_CASCADE = (
    "If gpt-5",
    "If claude-sonnet-4",
    "If gemini-2.5-pro",
)

CONVERT_RESPONSE_NODE = "Convert response to File"
# generation node -> merge that rejoins it with the routing item -> its converter.
# The Gemini branch already owned the shared converter, so it keeps that name.
REACTIONS_RESPONSE_BRANCHES = (
    ("(Re-)Generate code1", "MergeGPT-5", "Convert response to File GPT-5"),
    ("(Re-)Generate code3", "MergeClaude", "Convert response to File Claude"),
    ("(Re-)Generate Code2", "MergeGemini", CONVERT_RESPONSE_NODE),
)

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
    payload = normalize_workflow_shape(payload)
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
        generation["parameters"]["text"] = cloud_prompt_request(language)
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": prompt_generation_system_message(language)}
        ]
        old_write_name = (
            "Write draft prompt to disk"
            if "Write draft prompt to disk" in nodes
            else WRITE_PROMPT_NODE
        )
        write_node = nodes[old_write_name]
        write_node["name"] = WRITE_PROMPT_NODE
        if old_write_name != WRITE_PROMPT_NODE:
            payload["connections"] = rename_connection_node(
                payload["connections"],
                old_write_name,
                WRITE_PROMPT_NODE,
            )
    else:
        generation = nodes["Generate Prompt with local Qwen"]
        generation["parameters"]["jsonBody"] = qwen_prompt_request(language)
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
    payload = normalize_workflow_shape(payload)
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
        generation["parameters"]["jsonBody"] = qwen_test_request(language)
        payload["name"] = payload["name"].removesuffix("_smoke")
    else:
        generation = nodes["(Re-)Generate test suite"]
        # The assembled prompt is built in one Set node so that the exact text
        # sent to the model is a value that can be archived, not an expression
        # that only ever existed inside the generation node.
        generation["parameters"]["text"] = "={{ $json.assembled_prompt }}"
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": test_generation_system_message(language)}
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
    payload = normalize_workflow_shape(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    if READ_PROMPT_FILES_NODE not in nodes or GENERATE_CODE_NODE not in nodes:
        raise ValueError("not a supported transformation-generation workflow")

    nodes[READ_PROMPT_FILES_NODE]["parameters"]["fileSelector"] = (
        f"=/data/task_prompts/{language}/*.txt"
    )
    _scope_transformation_assets(nodes, language)
    generation = nodes[GENERATE_CODE_NODE]
    generation["parameters"]["text"] = transformation_request()
    generation["parameters"].setdefault("messages", {})["messageValues"] = [
        {"message": transformation_system_message(language)}
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
    payload = normalize_workflow_shape(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    nodes[READ_PROMPT_FILES_NODE]["parameters"]["fileSelector"] = (
        "=/data/task_prompts/reactions/*.txt"
    )
    _scope_transformation_assets(nodes, "reactions")
    for generation_name in (
        "(Re-)Generate code1",
        "(Re-)Generate code3",
        "(Re-)Generate Code2",
    ):
        generation = nodes[generation_name]
        generation["parameters"]["text"] = transformation_request()
        # The matrix carried its own hand-written instruction, so the shared
        # one -- and every rule added to it, including the Reactions extra
        # rule -- never reached the model on this language.
        generation["parameters"].setdefault("messages", {})["messageValues"] = [
            {"message": transformation_system_message("reactions")}
        ]

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
    remove_connection_targets(connections, obsolete)

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
            {"node": REACTIONS_MODEL_CASCADE[0], "type": "main", "index": 0},
        ]]
    }
    _cascade_reactions_model_branches(connections)
    return _convert_every_reactions_response(payload)


def _cascade_reactions_model_branches(connections: dict[str, Any]) -> None:
    """Offer the run's model to one branch at a time, not to all three at once.

    The three model conditions used to hang off the same node, so n8n ran the
    matching branch first and then drained the two that could not match. Their
    false output goes nowhere, which left the workflow ending on an ``If`` with
    no items -- and a subworkflow returns the last executed node's data, so the
    master received nothing even though the response had been written. Chaining
    the conditions leaves exactly one live path, ending at the write node, the
    way a single-model language workflow already ends.
    """
    for current, following in zip(
        REACTIONS_MODEL_CASCADE, REACTIONS_MODEL_CASCADE[1:]
    ):
        outputs = connections[current]["main"]
        while len(outputs) < 2:
            outputs.append([])
        outputs[1] = [{"node": following, "type": "main", "index": 0}]
    outputs = connections[REACTIONS_MODEL_CASCADE[-1]]["main"]
    while len(outputs) < 2:
        outputs.append([])
    outputs[1] = []


def _convert_every_reactions_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert the response on every model branch, not only the Gemini one.

    ``Write response to disk`` writes a binary property, and only ``Convert
    response to File`` produces one. In the matrix workflow that converter sat
    on the Gemini branch alone, so the gpt-5 and Claude branches reached the
    write node with a plain item and failed with "The item has no binary field
    'data'". Every other language runs ``generate -> convert -> write``; giving
    each branch its own converter is that same chain, and it keeps a branch's
    merge fed only when that branch actually ran.
    """
    template = next(
        node for node in payload["nodes"] if node["name"] == CONVERT_RESPONSE_NODE
    )
    connections = payload["connections"]
    for generation, merge, converter in REACTIONS_RESPONSE_BRANCHES:
        if not any(node["name"] == converter for node in payload["nodes"]):
            clone = json.loads(json.dumps(template))
            clone["name"] = converter
            clone["id"] = re.sub(r"[^a-z0-9]+", "-", converter.lower()).strip("-")
            generation_node = next(
                node for node in payload["nodes"] if node["name"] == generation
            )
            clone["position"] = [
                template["position"][0],
                generation_node["position"][1],
            ]
            payload["nodes"].append(clone)
        connections[generation] = {
            "main": [[{"node": converter, "type": "main", "index": 0}]]
        }
        connections[converter] = {
            "main": [[{"node": merge, "type": "main", "index": 1}]]
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
            if language_model and connection_targets(
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


def _scope_transformation_assets(nodes: dict[str, Any], language: str) -> None:
    """Read the transformation asset tree, not the test one.

    Both trees used to claim ``/data/examples``, ``/data/grammar`` and
    ``/data/helper_methods``. One container can bind each path to one host
    tree, and the instance that runs the master binds the test tree — so the
    transformation subworkflows read a directory that holds a differently named
    examples file and no helper methods, and their readers returned no items.
    Reactions stops dead on that (its static-file merge has no optional
    branch); the other three languages silently drop the examples section.
    Giving the transformation assets their own mount root keeps the two trees
    from shadowing each other.
    """
    for node_name, selector in (
        ("Read few shot examples", f"=/data/transformations/examples/{language}/Examples.txt"),
        ("Read Grammar", f"/data/transformations/grammar/{language}/EBNF.txt"),
        ("Read helper methods", f"=/data/transformations/helper_methods/{language}/*"),
    ):
        node = nodes.get(node_name)
        if node is not None:
            node["parameters"]["fileSelector"] = selector


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
    remove_connection_targets(connections, obsolete | {PROMPT_INPUT_NODE})
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
    remove_connection_targets(connections, set(CONTRACT_NODES))

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
                                qwen_assembled_prompt()
                                if is_qwen
                                else cloud_test_request(language)
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


def _response_identity(payload: dict[str, Any]) -> tuple[str, str]:
    write_node = next(
        node for node in payload["nodes"] if node["name"] == "Write response to disk"
    )
    match = RESPONSE_IDENTITY.search(write_node["parameters"]["fileName"])
    if match is None:
        raise ValueError("cannot infer model and strategy from response path")
    return match.group(1), match.group(2)
