"""How diagnosis names the cases and assertions of ``semantic_cases.json``.

The method name of a case comes from the renderers' own rule,
``codegen.java_rendering.rendered_method_name``, re-exported here.

Preparation and report assembly both read these rules from here, so they
cannot name the same case or assertion in two different ways.
"""

from __future__ import annotations

from typing import Any, Mapping

from llm4mtl.semantic_tests.codegen.java_rendering import rendered_method_name

__all__ = ["POSITIONAL_ASSERTION_ID", "assertion_id", "case_id", "rendered_method_name"]

# An assertion without its own ``id`` is named by its 1-based position.
POSITIONAL_ASSERTION_ID = "assertion-{position:03d}"


def case_id(test_case: Mapping[str, Any]) -> str:
    """The id a report uses for a case: its ``id``, else its ``name``."""
    return str(test_case.get("id") or test_case.get("name") or "")


def assertion_id(assertion: Mapping[str, Any], position: int) -> str:
    """The id of the assertion at 1-based ``position`` in its case."""
    positional_id = POSITIONAL_ASSERTION_ID.format(position=position)
    return str(assertion.get("id") or positional_id)
