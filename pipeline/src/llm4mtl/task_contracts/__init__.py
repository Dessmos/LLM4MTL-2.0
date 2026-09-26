"""Deterministic task model contracts as enforced ground truth.

Contracts keep infrastructure bindings (metamodel URIs, runtime model names,
``.ecore`` files, XML namespaces) out of the LLM's hands. The LLM supplies only
the semantics (input models and expected target-model facts). This package
rewrites the bindings from ``benchmark/tasks/<language>/task_contracts/<task>.json``
and rejects assertions on types the metamodels do not define.
"""

from __future__ import annotations

from llm4mtl.task_contracts.enforcement import enforce_contract
from llm4mtl.task_contracts.loader import contract_from_mapping, load_task_contract
from llm4mtl.task_contracts.models import ModelContract, TaskContract
from llm4mtl.task_contracts.render import contract_header_markdown

__all__ = [
    "ModelContract",
    "TaskContract",
    "contract_from_mapping",
    "contract_header_markdown",
    "enforce_contract",
    "load_task_contract",
]
