"""Which exports on disk are synchronized, and the command that rewrites them.

The repository walk: which workflow files each generation stage owns, how a
file's language and model are inferred from where it lives, and the `--write`
command that rewrites them in place.

Generated output is never the source of truth for its generator. The exports
under `workflows/n8n/` are produced from here and are never hand-edited: fix a
synchronizer or a prompt and run the command again.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from llm4mtl.conventions import LANGUAGE_CONFIGS, n8n_workflows_root
from llm4mtl.paths import TARGET
from llm4mtl.prompt_assembly.n8n_exports.synchronizers import (
    GENERATE_CODE_NODE,
    GENERATE_PROMPT_NODE,
    READ_PROMPT_FILES_NODE,
    synchronize_prompt_generation,
    synchronize_reactions_matrix,
    synchronize_test_generation,
    synchronize_transformation_generation,
)


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


def _model_from_filename(path: Path) -> str:
    for model in MODELS:
        if model in path.name:
            return model
    raise ValueError(f"cannot infer model from {path}")


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
