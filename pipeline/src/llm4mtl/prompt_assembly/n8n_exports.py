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
RESPONSE_IDENTITY = re.compile(r"/responses/([^/]+)/([^/]+)/")


@dataclass(frozen=True)
class WorkflowInputs:
    display_name: str
    reference_extension: str


INPUTS = {
    "etl": WorkflowInputs(
        display_name="Epsilon Transformation Language (ETL)",
        reference_extension="etl",
    ),
    "atl": WorkflowInputs(
        display_name="ATLAS Transformation Language (ATL)",
        reference_extension="atl",
    ),
    "qvto": WorkflowInputs(
        display_name="QVT Operational (QVT-O)",
        reference_extension="qvto",
    ),
    "reactions": WorkflowInputs(
        display_name="Vitruv Reactions Language",
        reference_extension="reactions",
    ),
}

PROMPT_INPUT_NODE = "Resolve exact task inputs"
OBSOLETE_INPUT_NODES = {
    PROMPT_INPUT_NODE,
    "Extract text from reference file",
    "Read model files",
    "Extract text from model files",
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
    inputs = INPUTS[language]
    nodes = {node["name"]: node for node in payload["nodes"]}
    nodes["Read reference file"]["parameters"]["fileSelector"] = (
        "=/data/benchmark/tasks/"
        f"{language}/references/*.{inputs.reference_extension}"
    )
    save_name = (
        "Save reaction name"
        if "Save reaction name" in nodes
        else "Save file name"
    )

    if "Generate Prompt from Input" in nodes:
        generation = nodes["Generate Prompt from Input"]
        generation["parameters"]["text"] = _cloud_prompt_request(language)
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": _prompt_generation_system_message(language)}
        ]
        old_write_name = (
            "Write draft prompt to disk"
            if "Write draft prompt to disk" in nodes
            else "Write prompt to disk"
        )
        write_node = nodes[old_write_name]
        write_node["name"] = "Write prompt to disk"
        if old_write_name != "Write prompt to disk":
            payload["connections"] = _rename_connection_node(
                payload["connections"],
                old_write_name,
                "Write prompt to disk",
            )
    else:
        generation = nodes["Generate Prompt with local Qwen"]
        generation["parameters"]["jsonBody"] = _qwen_prompt_request(language)
        write_node = nodes["Write prompt to disk"]
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
    _response_identity(payload)
    nodes = {node["name"]: node for node in payload["nodes"]}
    is_qwen = "Read Qwen prompt files" in nodes
    prompt_node_name = "Read Qwen prompt files" if is_qwen else "Read prompt files"
    nodes[prompt_node_name]["parameters"]["fileSelector"] = (
        f"=/data/task_prompts/{language}/*.txt"
    )

    if is_qwen:
        nodes["Save task name"]["parameters"]["assignments"]["assignments"][0][
            "value"
        ] = "={{$binary.data.fileName.replace(/\\.txt$/, '')}}"
        generation = nodes["Generate Test Suite with local Qwen"]
        generation["parameters"]["jsonBody"] = _qwen_test_request(language)
        payload["name"] = payload["name"].removesuffix("_smoke")
    else:
        generation = nodes["(Re-)Generate test suite"]
        generation["parameters"]["text"] = _cloud_test_request(language)
        generation["parameters"]["messages"]["messageValues"] = [
            {"message": _test_generation_system_message(language)}
        ]
    payload = _replace_language_wide_models(
        payload,
        language=language,
        save_name="Save task name" if is_qwen else "Save file name",
        merge_name=(
            "Merge prompt, task and models" if is_qwen else "Merge"
        ),
        merge_input=2 if is_qwen else 1,
    )
    return payload


def synchronize_transformation_generation(
    payload: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """Make transformation generation use the shared prompt and exact models."""
    nodes = {node["name"]: node for node in payload["nodes"]}
    if "Read prompt files" not in nodes or "(Re-)Generate code" not in nodes:
        raise ValueError("not a supported transformation-generation workflow")

    nodes["Read prompt files"]["parameters"]["fileSelector"] = (
        f"=/data/task_prompts/{language}/*.txt"
    )
    generation = nodes["(Re-)Generate code"]
    generation["parameters"]["text"] = generation["parameters"]["text"].replace(
        "$json.concatenated_model",
        "$json.metamodel_text",
    )
    save_name = (
        "Save file name"
        if "Save file name" in nodes
        else "Save reaction name"
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
    nodes = {node["name"]: node for node in payload["nodes"]}
    nodes["Read prompt files"]["parameters"]["fileSelector"] = (
        "=/data/task_prompts/reactions/*.txt"
    )
    for generation_name in (
        "(Re-)Generate code1",
        "(Re-)Generate code3",
        "(Re-)Generate Code2",
    ):
        generation = nodes[generation_name]
        generation["parameters"]["text"] = generation["parameters"]["text"].replace(
            "$json.concatenated_model",
            "$json.metamodel_text",
        )

    obsolete = {
        "Read model files",
        "Extract text from model files",
        "Summarize",
        PROMPT_INPUT_NODE,
        "Merge prompt and exact inputs",
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
            "name": "Merge prompt and exact inputs",
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

    trigger = connections["When clicking ‘Execute workflow’"]["main"][0]
    trigger[:] = [
        target for target in trigger if target["node"] not in obsolete
    ]
    connections["Extract text from examples file"]["main"][0][0]["index"] = 0
    connections["Extract text from grammar"]["main"][0][0]["index"] = 1
    connections["Extract text from helper methods"]["main"][0][0]["index"] = 2

    connections["Save reaction name"] = {
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
                "node": "Merge prompt and exact inputs",
                "type": "main",
                "index": 0,
            }
        ]]
    }
    connections[PROMPT_INPUT_NODE] = {
        "main": [[
            {
                "node": "Merge prompt and exact inputs",
                "type": "main",
                "index": 1,
            }
        ]]
    }
    connections["Merge prompt and exact inputs"] = {
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
            "main": [[{"node": "Read reference file", "type": "main", "index": 0}]]
        },
        "Read reference file": {
            "main": [[{"node": "Loop Over Items", "type": "main", "index": 0}]]
        },
        "Loop Over Items": {
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
            "main": [[{"node": "Convert prompt to file", "type": "main", "index": 0}]]
        }
    else:
        connections[generation_name] = {
            "main": [[{"node": "Convert prompt to file", "type": "main", "index": 0}]]
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
    connections["Convert prompt to file"] = {
        "main": [[{"node": "Write prompt to disk", "type": "main", "index": 0}]]
    }
    connections["Write prompt to disk"] = {
        "main": [[{"node": "Loop Over Items", "type": "main", "index": 0}]]
    }
    return connections


def _replace_language_wide_models(
    payload: dict[str, Any],
    *,
    language: str,
    save_name: str,
    merge_name: str,
    merge_input: int,
) -> dict[str, Any]:
    obsolete = {
        "Read model files",
        "Extract text from model files",
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


def _cloud_test_request(language: str) -> str:
    grammar_name = INPUTS[language].display_name
    return (
        '={{ $json.prompt + "\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        '($("Set Parameters").item.json.Few_shot ? '
        '"\\n\\n## Few-shot examples (guidance only)\\n" + '
        '$("Extract text from examples file").item.json.examples : "") + '
        '($("Set Parameters").item.json.Grammar ? '
        f'"\\n\\n## {grammar_name} grammar (syntax guidance only)\\n" + '
        '$("Extract text from grammar").item.json.grammar : "") + '
        '($("Set Parameters").item.json.Helper_methods ? '
        '"\\n\\n## Existing helper methods (background only)\\n" + '
        '$("Extract text from helper methods").item.json.helper_methods : "") }}'
    )


def _test_generation_system_message(language: str) -> str:
    message = (
        f"Generate semantic test artifacts for {INPUTS[language].display_name} "
        "from the reviewed shared task prompt. Follow that prompt and the exact "
        "task-specific metamodel files. Return only fenced file blocks: exactly "
        "one ```json file=semantic_cases.json block and the "
        "```xml file=models/<name>.model blocks it references. Never generate "
        "Java, JUnit, transformation code, Maven files, helper classes, or prose "
        "outside file blocks. semantic_cases.json must contain schemaVersion, "
        "testClass, transformation, metamodels, and tests. Each test contains "
        "name, models, and assertions; each model contains name, kind, role, "
        "path, generated, and metamodelUri only for EMF. Use only the canonical "
        "generic assertion kinds count, featureValues, objects, pathValues, and "
        "referencePairs. Every assertion uses expected; never use value, values, "
        "equals, ids, pairs, sourceType, targetType, where, or match. Assertions "
        "must describe observable target-model counts, feature values, links, "
        "and absence of unjustified elements."
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
        "{ role: 'user', content: ($json.prompt || '') + "
        "'\\n\\n## Authoritative metamodel files\\n' + "
        "($json.metamodel_text || '') }], "
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
    transformation_count = 0
    for language, config in sorted(LANGUAGE_CONFIGS.items()):
        root = n8n_workflows_root(config)
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
        for path in sorted((root / "test_generation").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            _write_json(
                path,
                synchronize_test_generation(payload, language),
            )
            test_count += 1
    transformation_root = TARGET.workflows / "transformations" / "workflows"
    for path in sorted(transformation_root.rglob("Prompt_generation*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        node_names = {node.get("name") for node in payload.get("nodes", [])}
        if "Generate Prompt from Input" not in node_names:
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
    for path in sorted(transformation_root.rglob("Prompting*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        node_names = {node.get("name") for node in payload.get("nodes", [])}
        if "(Re-)Generate code" not in node_names:
            continue
        language = _transformation_language(payload)
        _write_json(
            path,
            synchronize_transformation_generation(payload, language),
        )
        transformation_count += 1
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
        transformation_count += 1
    return prompt_count, test_count, transformation_count


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
    selector = nodes["Read prompt files"]["parameters"]["fileSelector"]
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
