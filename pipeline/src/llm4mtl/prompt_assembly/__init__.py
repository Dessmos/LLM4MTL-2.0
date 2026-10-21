"""Resolution of the exact repository inputs one prompt is built from.

Task prompt text is written by n8n's prompt-generation LLM and frozen under
``prompt_assets/task_prompts/``. Python's job here is the same for every
language: resolve a task to its reference transformation, the exact metamodel
files its contract names, and the language grammar. The raw contract is not
part of the LLM's input.
"""

from __future__ import annotations

from llm4mtl.prompt_assembly.task_inputs import (
    ResolvedTaskInputs,
    TaskInputResolutionError,
    resolve_custom_task_inputs,
    resolve_task_inputs,
)

__all__ = [
    "ResolvedTaskInputs",
    "TaskInputResolutionError",
    "resolve_custom_task_inputs",
    "resolve_task_inputs",
]
