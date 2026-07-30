"""Assemble an offline deterministic ETL prompt preview for one task.

This utility is retained for contract inspection and tests. The active
production flow resolves exact task inputs for an n8n LLM, reviews and freezes
its natural-language task prompt, and supplies that same prompt to both
downstream generators.
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
