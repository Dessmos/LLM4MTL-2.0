"""Assemble a fully deterministic test-generation prompt for one task.

This is the production prompt path. The older n8n ``prompt_generation`` stage is
kept only for draft prompt experiments; production prompts must be assembled
from deterministic task contracts and reference ETL so model names, metamodel
URIs, namespaces, and type names cannot be overwritten by another LLM.
"""

from __future__ import annotations

from llm4mtl.task_contracts import TaskContract, contract_header_block, task_context_block
from llm4mtl.prompt_assembly.template import PROMPT_BODY, PROMPT_INTRO


def build_test_generation_prompt(contract: TaskContract, reference_etl: str) -> str:
    """Return the full prompt: contract header + task context + static body."""
    sections = [
        contract_header_block(contract),
        "",
        PROMPT_INTRO,
        "",
        task_context_block(contract, reference_etl),
        "",
        PROMPT_BODY,
        "",
    ]
    return "\n".join(sections)
