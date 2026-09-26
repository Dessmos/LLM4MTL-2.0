"""What each n8n export is rewritten to do, workflow by workflow.

One synchronizer per kind of generation workflow. Each takes an exported
payload, rewrites the nodes and connections that must be the same in every
language, and returns the payload to write back. Prompt text comes from
`prompts`, node and connection helpers from `workflow_graph`, and node names
from `node_names`.

Every intended difference between the languages' workflows is made here.
Anything a synchronizer does not rewrite is unintended drift.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from llm4mtl.prompt_assembly.n8n_exports.node_names import (
    ASSEMBLE_PROMPT_NODE,
    CONVERT_ASSEMBLED_PROMPT_NODE,
    CONVERT_CANDIDATE_PROMPT_NODE,
    CONVERT_RESPONSE_NODE,
    EXAMPLES_TEXT_NODE,
    EXTRACT_CONTRACT_TEXT_NODE,
    EXTRACT_MODEL_TEXT_NODE,
    EXTRACT_PROMPT_TEXT_NODE,
    EXTRACT_QWEN_PROMPT_NODE,
    EXTRACT_REFERENCE_TEXT_NODE,
    GENERATE_CODE_NODE,
    GENERATE_PROMPT_NODE,
    GENERATE_PROMPT_QWEN_NODE,
    GENERATE_TEST_SUITE_NODE,
    GENERATE_TEST_SUITE_QWEN_NODE,
    GRAMMAR_TEXT_NODE,
    HELPER_METHODS_TEXT_NODE,
    LOOP_OVER_ITEMS_NODE,
    MERGE_MODELS_REFERENCE_GRAMMAR_NODE,
    MERGE_NODE,
    MERGE_PROMPT_INPUTS_NODE,
    MERGE_QWEN_TEST_INPUTS_NODE,
    PROMPT_INPUT_NODE,
    READ_EXAMPLES_NODE,
    READ_GRAMMAR_NODE,
    READ_HELPER_METHODS_NODE,
    READ_MODEL_FILES_NODE,
    READ_OUTPUT_CONTRACT_NODE,
    READ_PROMPT_FILES_NODE,
    READ_QWEN_PROMPT_FILES_NODE,
    READ_REFERENCE_FILE_NODE,
    SAVE_FILE_NAME_NODE,
    SAVE_REACTION_NAME_NODE,
    SAVE_TASK_NAME_NODE,
    STATIC_FILES_READY_NODE,
    SUMMARIZE_MODELS_NODE,
    SUMMARIZE_NODE,
    UPDATE_STRUCTURE_NODE,
    WRITE_DRAFT_PROMPT_NODE,
    WRITE_PROMPT_NODE,
    WRITE_RESPONSE_NODE,
)
from llm4mtl.prompt_assembly.n8n_exports.prompts import (
    ASSEMBLED_PROMPT_FIELD,
    INPUTS,
    OUTPUT_CONTRACT_FIELD,
    cloud_prompt_request,
    cloud_test_request,
    matrix_transformation_request,
    prompt_generation_system_message,
    qwen_assembled_prompt,
    qwen_prompt_request,
    qwen_test_request,
    test_generation_system_message,
    transformation_request,
    transformation_system_message,
)
from llm4mtl.prompt_assembly.n8n_exports.workflow_graph import (
    CONVERT_TO_FILE,
    EXTRACT_FROM_FILE,
    HTTP_REQUEST,
    MERGE,
    READ_WRITE_FILE,
    SET,
    TRIGGER_NODE,
    connect_in_sequence,
    connection_targets,
    drop_dangling_sources,
    main_edge,
    main_output,
    new_node,
    node_slug,
    normalize_workflow_shape,
    remove_connection_targets,
    remove_nodes,
    rename_connection_node,
)

# Paths and URLs as the n8n container sees them.
TASK_PROMPTS_DIR = "/data/task_prompts"
TASK_PROMPT_CANDIDATES_DIR = "/data/artifacts/task_prompt_candidates"
PROMPT_INPUTS_RESOLVE_URL = "http://stage-service:8129/prompt-inputs/resolve"

# A response path names its model and strategy: .../responses/<model>/<strategy>/...
RESPONSE_PATH = re.compile(r"/responses/[^/]+/[^/]+/")

# Output 1 of "Loop Over Items" runs once per item; output 0 runs when all are done.
LOOP_EACH_ITEM_OUTPUT = 1
# Output 1 of an "If" node carries the items that do not match.
IF_FALSE_OUTPUT = 1

# Where the new resolver node is drawn in each kind of workflow.
PROMPT_GENERATION_RESOLVER_POSITION = (-1376, 272)
TASK_WORKFLOW_RESOLVER_POSITION = (736, -368)
REACTIONS_MATRIX_RESOLVER_POSITION = (-448, 656)
REACTIONS_MATRIX_MERGE_POSITION = (-176, 784)

# The language-wide model inputs. The exact task inputs replace them.
LANGUAGE_WIDE_MODEL_NODES = frozenset(
    {
        READ_MODEL_FILES_NODE,
        EXTRACT_MODEL_TEXT_NODE,
        SUMMARIZE_NODE,
        SUMMARIZE_MODELS_NODE,
    }
)
# Prompt generation reads the reference, models, and grammar through the resolver.
OBSOLETE_PROMPT_INPUT_NODES = LANGUAGE_WIDE_MODEL_NODES | {
    PROMPT_INPUT_NODE,
    EXTRACT_REFERENCE_TEXT_NODE,
    READ_GRAMMAR_NODE,
    GRAMMAR_TEXT_NODE,
    MERGE_MODELS_REFERENCE_GRAMMAR_NODE,
}

# Transformation generation: the resolver feeds this input of the "Merge" node.
TRANSFORMATION_EXACT_INPUTS_MERGE_INPUT = 1

CONTRACT_NODES = frozenset(
    {
        READ_OUTPUT_CONTRACT_NODE,
        EXTRACT_CONTRACT_TEXT_NODE,
        ASSEMBLE_PROMPT_NODE,
        CONVERT_ASSEMBLED_PROMPT_NODE,
        WRITE_PROMPT_NODE,
    }
)

# The multi-model Reactions matrix exists for Reactions only.
MATRIX_LANGUAGE = "reactions"
MATRIX_OBSOLETE_NODES = frozenset(
    {
        READ_MODEL_FILES_NODE,
        EXTRACT_MODEL_TEXT_NODE,
        SUMMARIZE_NODE,
        PROMPT_INPUT_NODE,
        MERGE_PROMPT_INPUTS_NODE,
    }
)
# The merge that joins the frozen prompt with the exact task inputs.
PROMPT_TEXT_MERGE_INPUT = 0
EXACT_INPUTS_MERGE_INPUT = 1
# The static-file merge waits for these readers, on inputs 0, 1 and 2.
STATIC_FILE_TEXT_NODES = (
    EXAMPLES_TEXT_NODE,
    GRAMMAR_TEXT_NODE,
    HELPER_METHODS_TEXT_NODE,
)
# Tried in order; the first condition that matches the run's model wins.
REACTIONS_MODEL_CASCADE = (
    "If gpt-5",
    "If claude-sonnet-4",
    "If gemini-2.5-pro",
)
# generation node -> merge that rejoins it with the routing item -> its converter.
# The Gemini branch already owned the shared converter, so it keeps that name.
REACTIONS_RESPONSE_BRANCHES = (
    ("(Re-)Generate code1", "MergeGPT-5", "Convert response to File GPT-5"),
    ("(Re-)Generate code3", "MergeClaude", "Convert response to File Claude"),
    ("(Re-)Generate Code2", "MergeGemini", CONVERT_RESPONSE_NODE),
)
# A branch merge gets the routing item on input 0 and the response on input 1.
RESPONSE_MERGE_INPUT = 1

# Sets the model request on a generation node: (payload, nodes by name, language).
_RequestInstaller = Callable[[dict[str, Any], dict[str, Any], str], None]


@dataclass(frozen=True)
class _PromptGenerationVariant:
    """What differs between the cloud and the local-Qwen prompt generation."""

    generation_node: str
    # Nodes between the generation node and the candidate-prompt converter.
    post_processing_nodes: tuple[str, ...]
    install_request: _RequestInstaller


@dataclass(frozen=True)
class _ContractNodeLayout:
    """Where the output-contract nodes are drawn."""

    read_contract: tuple[int, int]
    extract_contract: tuple[int, int]
    assemble_prompt: tuple[int, int]
    convert_prompt: tuple[int, int]
    write_prompt: tuple[int, int]


@dataclass(frozen=True)
class _TestGenerationVariant:
    """What differs between the cloud and the local-Qwen test generation."""

    prompt_files_node: str
    save_name_node: str
    generation_node: str
    merge_node: str
    # The merge inputs that receive the exact task inputs and the output
    # contract. The contract comes last, so it also sets the number of inputs.
    exact_inputs_merge_input: int
    contract_merge_input: int
    contract_layout: _ContractNodeLayout
    install_request: _RequestInstaller
    # The assembled test prompt, as an n8n expression, for a language.
    assembled_prompt: Callable[[str], str]


def synchronize_prompt_generation(
    payload: dict[str, Any],
    language: str,
    model: str,
) -> dict[str, Any]:
    """Make prompt generation resolve exact inputs and write review candidates."""
    payload = normalize_workflow_shape(payload)
    nodes = _nodes_by_name(payload)
    variant = _prompt_generation_variant(nodes)
    save_name = (
        SAVE_REACTION_NAME_NODE
        if SAVE_REACTION_NAME_NODE in nodes
        else SAVE_FILE_NAME_NODE
    )
    _read_task_references(nodes[READ_REFERENCE_FILE_NODE], language)
    variant.install_request(payload, nodes, language)
    _write_prompt_candidates(nodes[WRITE_PROMPT_NODE], language, model, save_name)
    _replace_prompt_input_nodes(payload, language)
    payload["connections"] = _prompt_generation_connections(
        payload["connections"],
        variant,
        save_name,
    )
    return payload


def _prompt_generation_variant(nodes: dict[str, Any]) -> _PromptGenerationVariant:
    if GENERATE_PROMPT_NODE in nodes:
        return CLOUD_PROMPT_GENERATION
    return LOCAL_QWEN_PROMPT_GENERATION


def _read_task_references(read_node: dict[str, Any], language: str) -> None:
    extension = INPUTS[language].reference_extension
    read_node["parameters"]["fileSelector"] = (
        f"=/data/benchmark/tasks/{language}/references/*.{extension}"
    )


def _install_cloud_prompt_request(
    payload: dict[str, Any],
    nodes: dict[str, Any],
    language: str,
) -> None:
    generation = nodes[GENERATE_PROMPT_NODE]
    generation["parameters"]["text"] = cloud_prompt_request(language)
    generation["parameters"]["messages"]["messageValues"] = [
        {"message": prompt_generation_system_message(language)}
    ]
    if WRITE_DRAFT_PROMPT_NODE in nodes:
        _rename_draft_write_node(payload, nodes)


def _rename_draft_write_node(payload: dict[str, Any], nodes: dict[str, Any]) -> None:
    """Rename the old draft-writing node; it now writes review candidates."""
    write_node = nodes.pop(WRITE_DRAFT_PROMPT_NODE)
    write_node["name"] = WRITE_PROMPT_NODE
    nodes[WRITE_PROMPT_NODE] = write_node
    payload["connections"] = rename_connection_node(
        payload["connections"],
        WRITE_DRAFT_PROMPT_NODE,
        WRITE_PROMPT_NODE,
    )


def _install_qwen_prompt_request(
    payload: dict[str, Any],
    nodes: dict[str, Any],
    language: str,
) -> None:
    generation = nodes[GENERATE_PROMPT_QWEN_NODE]
    generation["parameters"]["jsonBody"] = qwen_prompt_request(language)
    payload["name"] = payload["name"].replace(
        "qwen2.5-coder-7b_smoke",
        "qwen2-5-coder-7b",
    )


CLOUD_PROMPT_GENERATION = _PromptGenerationVariant(
    generation_node=GENERATE_PROMPT_NODE,
    post_processing_nodes=(),
    install_request=_install_cloud_prompt_request,
)
LOCAL_QWEN_PROMPT_GENERATION = _PromptGenerationVariant(
    generation_node=GENERATE_PROMPT_QWEN_NODE,
    post_processing_nodes=(EXTRACT_QWEN_PROMPT_NODE,),
    install_request=_install_qwen_prompt_request,
)


def _write_prompt_candidates(
    write_node: dict[str, Any],
    language: str,
    model: str,
    save_name: str,
) -> None:
    write_node["parameters"]["fileName"] = (
        f"={TASK_PROMPT_CANDIDATES_DIR}/"
        f'{language}/{model}/{{{{ $node["{save_name}"].json.baseName }}}}.txt'
    )


def _replace_prompt_input_nodes(payload: dict[str, Any], language: str) -> None:
    """Swap the old input nodes for one call to the exact-inputs resolver.

    Their connections go too, because the caller rebuilds all connections.
    """
    payload["nodes"] = [
        node
        for node in payload["nodes"]
        if node["name"] not in OBSOLETE_PROMPT_INPUT_NODES
    ]
    payload["nodes"].append(
        _resolver_node(language, PROMPT_GENERATION_RESOLVER_POSITION)
    )


def _prompt_generation_connections(
    old_connections: dict[str, Any],
    variant: _PromptGenerationVariant,
    save_name: str,
) -> dict[str, Any]:
    """Rebuild every connection: reference, exact inputs, model, candidate file."""
    to_converter = (
        variant.generation_node,
        *variant.post_processing_nodes,
        CONVERT_CANDIDATE_PROMPT_NODE,
    )
    return {
        **connect_in_sequence(
            TRIGGER_NODE,
            READ_REFERENCE_FILE_NODE,
            LOOP_OVER_ITEMS_NODE,
        ),
        # Output 0 of the loop ("done") leads nowhere; output 1 handles each item.
        LOOP_OVER_ITEMS_NODE: {"main": [[], [main_edge(save_name)]]},
        **connect_in_sequence(save_name, PROMPT_INPUT_NODE, *to_converter),
        **_chat_models_feeding(old_connections, variant.generation_node),
        **connect_in_sequence(
            CONVERT_CANDIDATE_PROMPT_NODE,
            WRITE_PROMPT_NODE,
            LOOP_OVER_ITEMS_NODE,
        ),
    }


def _chat_models_feeding(
    connections: dict[str, Any],
    generation_name: str,
) -> dict[str, Any]:
    """The chat-model connections into ``generation_name``, kept as they are."""
    feeding: dict[str, Any] = {}
    for source_name, source_connections in connections.items():
        language_model = source_connections.get("ai_languageModel")
        if language_model and connection_targets(language_model, generation_name):
            feeding[source_name] = {"ai_languageModel": language_model}
    return feeding


def synchronize_test_generation(
    payload: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Make test generation consume the one frozen prompt for each task."""
    payload = normalize_workflow_shape(payload)
    nodes = _nodes_by_name(payload)
    response_path = _response_path(nodes)
    variant = _test_generation_variant(nodes)
    _read_frozen_prompts(nodes[variant.prompt_files_node], language)
    _scope_helper_methods(nodes, language)
    variant.install_request(payload, nodes, language)
    payload = _replace_language_wide_models(
        payload,
        language=language,
        save_name=variant.save_name_node,
        merge_name=variant.merge_node,
        merge_input=variant.exact_inputs_merge_input,
    )
    return _wire_output_contract(payload, language, variant, response_path)


def _response_path(nodes: dict[str, Any]) -> str:
    response_path = nodes[WRITE_RESPONSE_NODE]["parameters"]["fileName"]
    if RESPONSE_PATH.search(response_path) is None:
        raise ValueError("cannot infer model and strategy from response path")
    return response_path


def _test_generation_variant(nodes: dict[str, Any]) -> _TestGenerationVariant:
    if LOCAL_QWEN_TEST_GENERATION.prompt_files_node in nodes:
        return LOCAL_QWEN_TEST_GENERATION
    return CLOUD_TEST_GENERATION


def _install_cloud_test_request(
    _payload: dict[str, Any],
    nodes: dict[str, Any],
    language: str,
) -> None:
    generation = nodes[GENERATE_TEST_SUITE_NODE]
    # The prompt is assembled in a Set node, so the exact text sent to the
    # model is a value that can be archived.
    generation["parameters"]["text"] = f"={{{{ $json.{ASSEMBLED_PROMPT_FIELD} }}}}"
    generation["parameters"]["messages"]["messageValues"] = [
        {"message": test_generation_system_message(language)}
    ]


def _install_qwen_test_request(
    payload: dict[str, Any],
    nodes: dict[str, Any],
    language: str,
) -> None:
    task_name = nodes[SAVE_TASK_NAME_NODE]["parameters"]["assignments"]["assignments"]
    task_name[0]["value"] = "={{$binary.data.fileName.replace(/\\.txt$/, '')}}"
    generation = nodes[GENERATE_TEST_SUITE_QWEN_NODE]
    generation["parameters"]["jsonBody"] = qwen_test_request(language)
    payload["name"] = payload["name"].removesuffix("_smoke")


CLOUD_TEST_GENERATION = _TestGenerationVariant(
    prompt_files_node=READ_PROMPT_FILES_NODE,
    save_name_node=SAVE_FILE_NAME_NODE,
    generation_node=GENERATE_TEST_SUITE_NODE,
    merge_node=MERGE_NODE,
    exact_inputs_merge_input=1,
    contract_merge_input=6,
    contract_layout=_ContractNodeLayout(
        read_contract=(448, -160),
        extract_contract=(736, -160),
        assemble_prompt=(1232, -288),
        convert_prompt=(1440, -448),
        write_prompt=(1632, -448),
    ),
    install_request=_install_cloud_test_request,
    assembled_prompt=cloud_test_request,
)
LOCAL_QWEN_TEST_GENERATION = _TestGenerationVariant(
    prompt_files_node=READ_QWEN_PROMPT_FILES_NODE,
    save_name_node=SAVE_TASK_NAME_NODE,
    generation_node=GENERATE_TEST_SUITE_QWEN_NODE,
    merge_node=MERGE_QWEN_TEST_INPUTS_NODE,
    exact_inputs_merge_input=2,
    contract_merge_input=3,
    contract_layout=_ContractNodeLayout(
        read_contract=(-512, 96),
        extract_contract=(-288, 96),
        assemble_prompt=(208, -288),
        convert_prompt=(432, -448),
        write_prompt=(656, -448),
    ),
    install_request=_install_qwen_test_request,
    # The local-Qwen prompt has no optional sections, so it is the same in
    # every language.
    assembled_prompt=lambda _language: qwen_assembled_prompt(),
)


def _wire_output_contract(
    payload: dict[str, Any],
    language: str,
    variant: _TestGenerationVariant,
    response_path: str,
) -> dict[str, Any]:
    """Deliver the output contract on every strategy and archive the prompt.

    The contract is not a prompting treatment, so it hangs off the loop
    directly and every prompting strategy gets it. Strategies differ only in
    their examples.

    The assembled prompt is written next to its response. Otherwise a response
    that breaks the contract cannot be told apart from a prompt that lacked it.
    """
    remove_nodes(payload, CONTRACT_NODES)
    payload["nodes"] += _output_contract_nodes(language, response_path, variant)
    _connect_output_contract(payload["connections"], variant)
    for node in payload["nodes"]:
        if node["name"] == variant.merge_node:
            node["parameters"]["numberInputs"] = variant.contract_merge_input + 1
    return payload


def _output_contract_nodes(
    language: str,
    response_path: str,
    variant: _TestGenerationVariant,
) -> list[dict[str, Any]]:
    layout = variant.contract_layout
    return [
        _read_contract_node(language, layout.read_contract),
        _extract_contract_node(language, layout.extract_contract),
        _assemble_prompt_node(
            variant.assembled_prompt(language),
            layout.assemble_prompt,
        ),
        _convert_assembled_prompt_node(layout.convert_prompt),
        _write_prompt_archive_node(response_path, layout.write_prompt),
    ]


def _read_contract_node(language: str, position: tuple[int, int]) -> dict[str, Any]:
    return new_node(
        READ_WRITE_FILE,
        name=READ_OUTPUT_CONTRACT_NODE,
        node_id=f"read-output-contract-{language}",
        position=position,
        parameters={
            "fileSelector": f"=/data/contract/{language}/semantic_cases_contract.txt",
            "options": {},
        },
    )


def _extract_contract_node(
    language: str,
    position: tuple[int, int],
) -> dict[str, Any]:
    return new_node(
        EXTRACT_FROM_FILE,
        name=EXTRACT_CONTRACT_TEXT_NODE,
        node_id=f"extract-text-from-contract-{language}",
        position=position,
        parameters={
            "operation": "text",
            "destinationKey": OUTPUT_CONTRACT_FIELD,
            "options": {},
        },
    )


def _assemble_prompt_node(
    assembled_prompt: str,
    position: tuple[int, int],
) -> dict[str, Any]:
    assignment = {
        "id": "assemble-prompt-assignments-1",
        "name": ASSEMBLED_PROMPT_FIELD,
        "value": assembled_prompt,
        "type": "string",
    }
    return new_node(
        SET,
        name=ASSEMBLE_PROMPT_NODE,
        node_id="assemble-prompt",
        position=position,
        parameters={
            "assignments": {"assignments": [assignment]},
            "includeOtherFields": True,
            "options": {},
        },
    )


def _convert_assembled_prompt_node(position: tuple[int, int]) -> dict[str, Any]:
    return new_node(
        CONVERT_TO_FILE,
        name=CONVERT_ASSEMBLED_PROMPT_NODE,
        node_id="convert-prompt-to-file",
        position=position,
        parameters={
            "operation": "toText",
            "sourceProperty": ASSEMBLED_PROMPT_FIELD,
            "binaryPropertyName": "data",
            "options": {},
        },
    )


def _write_prompt_archive_node(
    response_path: str,
    position: tuple[int, int],
) -> dict[str, Any]:
    return new_node(
        READ_WRITE_FILE,
        name=WRITE_PROMPT_NODE,
        node_id="write-prompt-to-disk",
        position=position,
        parameters={
            "operation": "write",
            "fileName": response_path.replace("/responses/", "/prompts/", 1),
            "dataPropertyName": "data",
            "options": {},
        },
    )


def _connect_output_contract(
    connections: dict[str, Any],
    variant: _TestGenerationVariant,
) -> None:
    """Loop -> contract -> merge -> assembled prompt -> model and prompt archive."""
    connections[LOOP_OVER_ITEMS_NODE]["main"][LOOP_EACH_ITEM_OUTPUT].append(
        main_edge(READ_OUTPUT_CONTRACT_NODE)
    )
    connections[READ_OUTPUT_CONTRACT_NODE] = main_output(
        main_edge(EXTRACT_CONTRACT_TEXT_NODE)
    )
    connections[EXTRACT_CONTRACT_TEXT_NODE] = main_output(
        main_edge(variant.merge_node, variant.contract_merge_input)
    )
    connections[variant.merge_node] = main_output(main_edge(ASSEMBLE_PROMPT_NODE))
    connections[ASSEMBLE_PROMPT_NODE] = main_output(
        main_edge(variant.generation_node),
        main_edge(CONVERT_ASSEMBLED_PROMPT_NODE),
    )
    connections[CONVERT_ASSEMBLED_PROMPT_NODE] = main_output(
        main_edge(WRITE_PROMPT_NODE)
    )


def _scope_helper_methods(nodes: dict[str, Any], language: str) -> None:
    """Read helper methods from this language's folder, like examples and grammars.

    A selector such as ``/data/helper_methods//*`` matches the language folders
    themselves, not the files inside them.
    """
    node = nodes.get(READ_HELPER_METHODS_NODE)
    if node is None:
        return
    node["parameters"]["fileSelector"] = f"=/data/helper_methods/{language}/*"


def synchronize_transformation_generation(
    payload: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Make transformation generation use the shared prompt and exact models."""
    payload = normalize_workflow_shape(payload)
    nodes = _nodes_by_name(payload)
    if READ_PROMPT_FILES_NODE not in nodes or GENERATE_CODE_NODE not in nodes:
        raise ValueError("not a supported transformation-generation workflow")

    _read_frozen_prompts(nodes[READ_PROMPT_FILES_NODE], language)
    _scope_transformation_assets(nodes, language)
    _install_transformation_request(
        nodes[GENERATE_CODE_NODE], language, transformation_request()
    )
    save_name = (
        SAVE_FILE_NAME_NODE if SAVE_FILE_NAME_NODE in nodes else SAVE_REACTION_NAME_NODE
    )
    return _replace_language_wide_models(
        payload,
        language=language,
        save_name=save_name,
        merge_name=MERGE_NODE,
        merge_input=TRANSFORMATION_EXACT_INPUTS_MERGE_INPUT,
    )


def _install_transformation_request(
    generation: dict[str, Any],
    language: str,
    request: str,
) -> None:
    generation["parameters"]["text"] = request
    generation["parameters"].setdefault("messages", {})["messageValues"] = [
        {"message": transformation_system_message(language)}
    ]


def _scope_transformation_assets(nodes: dict[str, Any], language: str) -> None:
    """Read the transformation asset tree, not the test one.

    A container binds each path to one host folder, and the n8n instance that
    runs the master workflow binds ``/data/examples`` and its siblings to the
    test assets. So transformation assets live under their own root,
    ``/data/transformations/``. Otherwise their readers return no items:
    Reactions then stops, and the other languages silently lose their examples.
    """
    for node_name, selector in (
        (
            READ_EXAMPLES_NODE,
            f"=/data/transformations/examples/{language}/Examples.txt",
        ),
        (READ_GRAMMAR_NODE, f"/data/transformations/grammar/{language}/EBNF.txt"),
        (
            READ_HELPER_METHODS_NODE,
            f"=/data/transformations/helper_methods/{language}/*",
        ),
    ):
        node = nodes.get(node_name)
        if node is not None:
            node["parameters"]["fileSelector"] = selector


def synchronize_reactions_matrix(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Use exact task inputs in the multi-model Reactions matrix workflow."""
    payload = normalize_workflow_shape(payload)
    nodes = _nodes_by_name(payload)
    _read_frozen_prompts(nodes[READ_PROMPT_FILES_NODE], MATRIX_LANGUAGE)
    _scope_transformation_assets(nodes, MATRIX_LANGUAGE)
    for generation_name, _merge, _converter in REACTIONS_RESPONSE_BRANCHES:
        # The shared instruction gives the matrix the same rules (including the
        # Reactions extra rule) as every other workflow. The request is the
        # matrix's own: it serves every strategy, so each item's strategy flags
        # choose the parts.
        _install_transformation_request(
            nodes[generation_name], MATRIX_LANGUAGE, matrix_transformation_request()
        )
    _drop_concatenated_model(nodes[UPDATE_STRUCTURE_NODE])
    _replace_matrix_input_nodes(payload)
    _wire_matrix_static_files(payload["connections"], nodes)
    _wire_matrix_exact_inputs(payload["connections"])
    _cascade_reactions_model_branches(payload["connections"])
    return _convert_every_reactions_response(payload)


def _drop_concatenated_model(update_structure: dict[str, Any]) -> None:
    assignments = update_structure["parameters"]["assignments"]
    assignments["assignments"] = [
        assignment
        for assignment in assignments["assignments"]
        if assignment["name"] != "concatenated_model"
    ]


def _replace_matrix_input_nodes(payload: dict[str, Any]) -> None:
    remove_nodes(payload, MATRIX_OBSOLETE_NODES)
    payload["nodes"].append(
        _resolver_node(MATRIX_LANGUAGE, REACTIONS_MATRIX_RESOLVER_POSITION)
    )
    payload["nodes"].append(
        new_node(
            MERGE,
            name=MERGE_PROMPT_INPUTS_NODE,
            node_id="merge-prompt-and-exact-inputs-reactions",
            position=REACTIONS_MATRIX_MERGE_POSITION,
            parameters={
                "mode": "combine",
                "combineBy": "combineByPosition",
                "numberInputs": 2,
                "options": {},
            },
        )
    )


def _wire_matrix_static_files(
    connections: dict[str, Any],
    nodes: dict[str, Any],
) -> None:
    """Without the model summary, the static-file merge waits for three readers."""
    for merge_input, reader in enumerate(STATIC_FILE_TEXT_NODES):
        connections[reader]["main"][0][0]["index"] = merge_input
    nodes[STATIC_FILES_READY_NODE]["parameters"]["numberInputs"] = len(
        STATIC_FILE_TEXT_NODES
    )


def _wire_matrix_exact_inputs(connections: dict[str, Any]) -> None:
    """Task name -> frozen prompt and exact inputs -> merge -> first model check."""
    connections[SAVE_REACTION_NAME_NODE] = main_output(
        main_edge(EXTRACT_PROMPT_TEXT_NODE),
        main_edge(PROMPT_INPUT_NODE),
    )
    connections[EXTRACT_PROMPT_TEXT_NODE] = main_output(
        main_edge(MERGE_PROMPT_INPUTS_NODE, PROMPT_TEXT_MERGE_INPUT)
    )
    connections[PROMPT_INPUT_NODE] = main_output(
        main_edge(MERGE_PROMPT_INPUTS_NODE, EXACT_INPUTS_MERGE_INPUT)
    )
    connections[MERGE_PROMPT_INPUTS_NODE] = main_output(
        main_edge(REACTIONS_MODEL_CASCADE[0])
    )


def _cascade_reactions_model_branches(connections: dict[str, Any]) -> None:
    """Chain the model conditions, so only one branch runs.

    A sub-workflow returns the data of its last executed node. If all three
    ``If`` nodes hang off the same node, the workflow can end on an ``If`` with
    no items, and the master receives nothing even though the response was
    written. With a chain there is one live path, and it ends at the write node.
    """
    for current, following in zip(REACTIONS_MODEL_CASCADE, REACTIONS_MODEL_CASCADE[1:]):
        _set_false_output(connections[current], [main_edge(following)])
    _set_false_output(connections[REACTIONS_MODEL_CASCADE[-1]], [])


def _set_false_output(
    condition_connections: dict[str, Any],
    edges: list[dict[str, Any]],
) -> None:
    outputs = condition_connections["main"]
    while len(outputs) <= IF_FALSE_OUTPUT:
        outputs.append([])
    outputs[IF_FALSE_OUTPUT] = edges


def _convert_every_reactions_response(payload: dict[str, Any]) -> dict[str, Any]:
    """Give every model branch its own response converter.

    ``Write response to disk`` needs a binary property, and only a ``Convert
    response to File`` node makes one. Without it a branch fails with "The item
    has no binary field 'data'". Each branch runs ``generate -> convert ->
    merge``, so a branch's merge is fed only when that branch ran.
    """
    nodes = _nodes_by_name(payload)
    connections = payload["connections"]
    for generation, merge, converter in REACTIONS_RESPONSE_BRANCHES:
        if converter not in nodes:
            template = nodes[CONVERT_RESPONSE_NODE]
            payload["nodes"].append(
                _converter_copy(template, converter, nodes[generation])
            )
        connections[generation] = main_output(main_edge(converter))
        connections[converter] = main_output(main_edge(merge, RESPONSE_MERGE_INPUT))
    return payload


def _converter_copy(
    template: dict[str, Any],
    name: str,
    generation: dict[str, Any],
) -> dict[str, Any]:
    """A copy of the shared converter, drawn on the row of its generation node."""
    converter = copy.deepcopy(template)
    converter["name"] = name
    converter["id"] = node_slug(name)
    converter["position"] = [template["position"][0], generation["position"][1]]
    return converter


def _nodes_by_name(payload: dict[str, Any]) -> dict[str, Any]:
    return {node["name"]: node for node in payload["nodes"]}


def _read_frozen_prompts(read_node: dict[str, Any], language: str) -> None:
    read_node["parameters"]["fileSelector"] = f"={TASK_PROMPTS_DIR}/{language}/*.txt"


def _resolver_node(language: str, position: tuple[int, int]) -> dict[str, Any]:
    """The stage-service call that returns the exact inputs of one task."""
    return new_node(
        HTTP_REQUEST,
        name=PROMPT_INPUT_NODE,
        node_id=f"resolve-exact-task-inputs-{language}",
        position=position,
        parameters={
            "method": "POST",
            "url": PROMPT_INPUTS_RESOLVE_URL,
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": (
                "={{ { language: " f"'{language}', task: $json.baseName" " } }}"
            ),
            "options": {},
        },
    )


def _replace_language_wide_models(
    payload: dict[str, Any],
    *,
    language: str,
    save_name: str,
    merge_name: str,
    merge_input: int,
) -> dict[str, Any]:
    """Feed the task name into the resolver, and the resolver into the merge."""
    remove_nodes(payload, LANGUAGE_WIDE_MODEL_NODES)
    _replace_resolver_node(payload, language)
    connections = payload["connections"]
    save_outputs = connections.setdefault(save_name, {}).setdefault("main", [[]])
    if not save_outputs:
        save_outputs.append([])
    save_outputs[0].append(main_edge(PROMPT_INPUT_NODE))
    connections[PROMPT_INPUT_NODE] = main_output(main_edge(merge_name, merge_input))
    drop_dangling_sources(payload)
    return payload


def _replace_resolver_node(payload: dict[str, Any], language: str) -> None:
    """Put in a fresh resolver node and remove every edge into it.

    Its outgoing entry stays in ``connections``, so the caller's replacement
    keeps the same position in the exported JSON.
    """
    payload["nodes"] = [
        node for node in payload["nodes"] if node["name"] != PROMPT_INPUT_NODE
    ]
    payload["nodes"].append(_resolver_node(language, TASK_WORKFLOW_RESOLVER_POSITION))
    remove_connection_targets(payload["connections"], {PROMPT_INPUT_NODE})
