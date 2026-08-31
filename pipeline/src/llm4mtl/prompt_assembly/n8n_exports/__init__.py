"""Synchronize the n8n task-prompt and generation workflow exports.

The prompt-generation LLM receives one reference plus only the metamodels named
by that task's contract and produces a candidate natural-language task prompt.
After review, one frozen prompt per task is the common input to transformation
generation and semantic-test generation.

The exports under ``workflows/n8n/`` are generated from this package. Fix a
prompt or a synchronizer and re-run the command; never hand-edit the JSON::

    python -m llm4mtl.prompt_assembly.n8n_exports --write

Read the module that answers your question:

* :mod:`~llm4mtl.prompt_assembly.n8n_exports.prompts` — the exact text every
  model receives, and the per-language facts it interpolates. No n8n knowledge.
* :mod:`~llm4mtl.prompt_assembly.n8n_exports.workflow_graph` — generic n8n node
  and connection mechanics. No prompt knowledge.
* :mod:`~llm4mtl.prompt_assembly.n8n_exports.synchronizers` — what each
  generation workflow is rewritten to do, and why.
* :mod:`~llm4mtl.prompt_assembly.n8n_exports.sync` — which files on disk are
  rewritten, and the command that does it.

This facade exposes the command and the four payload transforms. Anything else
is imported from the module that owns it, so a reader can tell what kind of
thing it is from where it came.
"""

from __future__ import annotations

from llm4mtl.prompt_assembly.n8n_exports.sync import (
    main,
    parse_args,
    synchronize_exports,
)
from llm4mtl.prompt_assembly.n8n_exports.synchronizers import (
    synchronize_prompt_generation,
    synchronize_reactions_matrix,
    synchronize_test_generation,
    synchronize_transformation_generation,
)

__all__ = [
    "main",
    "parse_args",
    "synchronize_exports",
    "synchronize_prompt_generation",
    "synchronize_reactions_matrix",
    "synchronize_test_generation",
    "synchronize_transformation_generation",
]
