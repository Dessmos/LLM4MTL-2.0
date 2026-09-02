"""Behavior locks for deterministic task-contract enforcement helpers."""

from __future__ import annotations

import unittest

from llm4mtl.task_contracts.enforcement import (
    _declared_top_level_metamodels,
    _validate_assertion_types,
)
from llm4mtl.task_contracts.models import ModelContract


def _model_contract(*, kind: str = "emf") -> ModelContract:
    return ModelContract(
        runtime_name="OUT",
        roles=("target",),
        kind=kind,
        metamodel_uri="urn:target",
        metamodel_ns_prefix="target",
        metamodel_alias="Target",
        metamodel_file="Target.ecore",
        types_used_in_transformation=("Node",),
        available_types=("Node", "Edge"),
    )


class DeclaredMetamodelTests(unittest.TestCase):

    def test_declarations_preserve_order_and_key_precedence(self) -> None:
        spec = {
            "metamodels": [
                {"uri": "urn:first", "name": "IgnoredName"},
                {"uri": "", "metamodelUri": "urn:second", "name": "Ignored"},
                "metamodels/Third.ecore",
                {},
                "",
            ]
        }

        self.assertEqual(
            ["urn:first", "urn:second", "Third"],
            _declared_top_level_metamodels(spec),
        )


class AssertionTypeValidationTests(unittest.TestCase):

    def test_only_unknown_emf_types_add_a_violation(self) -> None:
        assertions = [
            {"model": "OUT", "type": "Missing"},
            {"model": "OUT", "type": "Node"},
            {"model": "UNKNOWN", "type": "Missing"},
            "not-an-assertion",
        ]
        violations: list[str] = []

        _validate_assertion_types(
            assertions,
            {"OUT": _model_contract()},
            violations,
            test_index=3,
        )

        self.assertEqual(
            [
                "test #3 assertion #1: type 'OUT!Missing' is not defined in "
                "metamodel 'urn:target' (available: Node, Edge)"
            ],
            violations,
        )

    def test_plain_xml_types_are_not_emf_contract_violations(self) -> None:
        violations: list[str] = []

        _validate_assertion_types(
            [{"model": "OUT", "type": "AnyElement"}],
            {"OUT": _model_contract(kind="plainXml")},
            violations,
            test_index=1,
        )

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
