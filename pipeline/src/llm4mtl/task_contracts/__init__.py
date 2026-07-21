"""Deterministic task model contracts as enforced ground truth.

The contract layer keeps infrastructure bindings (metamodel URIs, runtime model
names, ``.ecore`` files, XML namespaces) out of the LLM's hands: the LLM only
supplies semantics (input models and expected target-model facts), while this
layer rewrites the bindings from the ``task_contracts/<task>.json`` source of
truth and rejects assertions over types the metamodels do not define.
"""

from __future__ import annotations

from llm4mtl.task_contracts.enforcement import enforce_contract
from llm4mtl.task_contracts.loader import contract_from_mapping, load_task_contract
from llm4mtl.task_contracts.models import ModelContract, TaskContract
from llm4mtl.task_contracts.render import (
    contract_header_block,
    contract_header_markdown,
    task_context_block,
    task_context_markdown,
)

__all__ = [
    "ModelContract",
    "TaskContract",
    "contract_from_mapping",
    "contract_header_block",
    "contract_header_markdown",
    "enforce_contract",
    "load_task_contract",
    "task_context_block",
    "task_context_markdown",
]
