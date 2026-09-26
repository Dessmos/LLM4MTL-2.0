"""The adapter for the old Tree2Graph expectedNodes/expectedEdges shape.

These tests record what the adapter does today. Whether the adapter should
exist at all is an open research decision, so they pin its behaviour and do
not judge it.
"""

from __future__ import annotations

import unittest

from llm4mtl.semantic_tests.extraction.semantic_cases.errors import SemanticCasesError
from llm4mtl.semantic_tests.extraction.semantic_cases.legacy_adapter import (
    expected_edge_pairs,
    expected_node_names,
    is_legacy_tree2graph_spec,
    normalize_legacy_tree2graph_spec,
)


def legacy_test(**overrides: object) -> dict[str, object]:
    test: dict[str, object] = {
        "name": "twoNodes",
        "inputModel": "models/tree.model",
        "expectedNodes": ["root", {"name": "leaf"}],
        "expectedEdges": [{"source": "root", "target": "leaf"}],
    }
    test.update(overrides)
    return test


class LegacyShapeDetectionTests(unittest.TestCase):

    def test_a_test_with_expected_nodes_and_no_models_is_legacy(self) -> None:
        cases = {
            "one legacy test": {"tests": [legacy_test()]},
            "legacy test after a canonical one": {
                "tests": [{"name": "canonical"}, legacy_test()]
            },
        }
        for label, spec in cases.items():
            with self.subTest(label):
                self.assertTrue(is_legacy_tree2graph_spec(spec))

    def test_other_shapes_are_not_legacy(self) -> None:
        cases = {
            "spec-level models present": {
                "models": [],
                "tests": [legacy_test()],
            },
            "empty tests": {"tests": []},
            "no tests key": {},
            "tests is not a list": {"tests": legacy_test()},
            "no test has expectedNodes": {"tests": [{"name": "canonical"}]},
            "expectedNodes only in a non-object entry": {"tests": ["expectedNodes"]},
        }
        for label, spec in cases.items():
            with self.subTest(label):
                self.assertFalse(is_legacy_tree2graph_spec(spec))


class LegacyExpectationValidationTests(unittest.TestCase):

    def test_node_names_accept_strings_and_named_objects(self) -> None:
        self.assertEqual(
            ["root", "leaf"], expected_node_names(["root", {"name": "leaf"}])
        )

    def test_invalid_node_expectations_are_rejected(self) -> None:
        cases = {
            "not a list": ({"name": "root"}, "expectedNodes must be an array"),
            "number entry": ([1], "entries must be strings or objects with a name"),
            "object without name": (
                [{"label": "root"}],
                "entries must be strings or objects with a name",
            ),
            "object with non-string name": (
                [{"name": 3}],
                "entries must be strings or objects with a name",
            ),
        }
        for label, (raw_nodes, message) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(SemanticCasesError, message):
                    expected_node_names(raw_nodes)

    def test_edge_pairs_are_joined_with_an_arrow(self) -> None:
        self.assertEqual(
            ["root->leaf"],
            expected_edge_pairs([{"source": "root", "target": "leaf"}]),
        )

    def test_invalid_edge_expectations_are_rejected(self) -> None:
        cases = {
            "not a list": ("root->leaf", "expectedEdges must be an array"),
            "string entry": (["root->leaf"], "must contain source and target"),
            "missing target": ([{"source": "root"}], "must contain source and target"),
            "empty source": (
                [{"source": "", "target": "leaf"}],
                "must contain source and target",
            ),
        }
        for label, (raw_edges, message) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(SemanticCasesError, message):
                    expected_edge_pairs(raw_edges)

    def test_an_invalid_test_rejects_the_whole_spec(self) -> None:
        spec = {"tests": [legacy_test(expectedEdges=[{"source": "root"}])]}

        with self.assertRaises(SemanticCasesError):
            normalize_legacy_tree2graph_spec(spec)


class LegacyNormalizationTests(unittest.TestCase):

    def test_a_legacy_test_becomes_four_graph_assertions(self) -> None:
        spec = {"testClass": "LegacyTest", "tests": [legacy_test()]}

        self.assertEqual(
            {
                "schemaVersion": 1,
                "testClass": "LegacyTest",
                "transformation": "transformations/Tree2Graph.etl",
                "metamodels": ["metamodels/Tree.ecore", "metamodels/Graph.ecore"],
                "tests": [
                    {
                        "name": "twoNodes",
                        "models": [
                            {
                                "name": "Tree",
                                "kind": "emf",
                                "role": "source",
                                "path": "models/tree.model",
                                "generated": True,
                                "metamodelUri": "Tree",
                            },
                            {
                                "name": "Graph",
                                "kind": "emf",
                                "role": "target",
                                "metamodelUri": "Graph",
                            },
                        ],
                        "assertions": [
                            {
                                "kind": "count",
                                "model": "Graph",
                                "type": "Node",
                                "expected": 2,
                            },
                            {
                                "kind": "count",
                                "model": "Graph",
                                "type": "Edge",
                                "expected": 1,
                            },
                            {
                                "kind": "featureValues",
                                "model": "Graph",
                                "type": "Node",
                                "feature": "name",
                                "expected": ["root", "leaf"],
                            },
                            {
                                "kind": "referencePairs",
                                "model": "Graph",
                                "type": "Edge",
                                "source": "source.name",
                                "target": "target.name",
                                "expected": [{"source": "root", "target": "leaf"}],
                            },
                        ],
                    }
                ],
            },
            normalize_legacy_tree2graph_spec(spec),
        )

    def test_a_missing_test_class_gets_the_tree2graph_default(self) -> None:
        normalized = normalize_legacy_tree2graph_spec({"tests": [legacy_test()]})

        self.assertEqual("GeneratedTree2GraphSemanticTest", normalized["testClass"])

    def test_an_edge_source_is_split_at_the_first_arrow(self) -> None:
        spec = {
            "tests": [
                legacy_test(expectedEdges=[{"source": "a->b", "target": "c"}])
            ]
        }

        pairs = normalize_legacy_tree2graph_spec(spec)["tests"][0]["assertions"][3]

        self.assertEqual([{"source": "a", "target": "b->c"}], pairs["expected"])


if __name__ == "__main__":
    unittest.main()
