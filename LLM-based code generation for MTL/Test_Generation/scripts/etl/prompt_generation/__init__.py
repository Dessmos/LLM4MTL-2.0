"""Deterministic assembly of ETL test-generation prompts.

The prompt-generation LLM used to author the transformation/metamodel section
freely, which leaked Tree2Graph context into other tasks. Here that section is
built from the task contract and the verbatim reference ETL, leaving only the
semantic answer to the downstream LLM.
"""

from __future__ import annotations

from etl.prompt_generation.builder import build_test_generation_prompt

__all__ = ["build_test_generation_prompt"]
