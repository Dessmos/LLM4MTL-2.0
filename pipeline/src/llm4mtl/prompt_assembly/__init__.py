"""Resolution of the exact repository inputs one prompt is built from.

Prompt text itself is authored by n8n's prompt-generation LLM and frozen under
``prompt_assets/task_prompts/``. Python's job here is narrower and identical for
every language: resolve a task to its reference transformation, the exact
metamodel files its contract names, and the language grammar — and keep the raw
contract out of the LLM's input.
"""

from __future__ import annotations

from llm4mtl.prompt_assembly.task_inputs import (
    ResolvedTaskInputs,
    TaskInputResolutionError,
    resolve_task_inputs,
)

__all__ = [
    "ResolvedTaskInputs",
    "TaskInputResolutionError",
    "resolve_task_inputs",
]
