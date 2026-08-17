"""Characterize deterministic Java assertion dispatch for every supported kind."""

from __future__ import annotations

import unittest
from typing import Any, Callable

from llm4mtl.languages.java_assertions import render_assertions
from llm4mtl.semantic_tests.codegen.java import render_assertion


ASSERTIONS = (
    {"kind": "count", "model": "OUT", "type": "Node", "expected": 2},
    {
        "kind": "featureValues",
        "model": "OUT",
        "type": "Node",
        "feature": "name",
        "expected": ["first", "second"],
    },
    {
        "kind": "pathValues",
        "model": "OUT",
        "type": "Node",
        "path": "parent.name",
        "expected": ["root"],
        "contains": True,
    },
    {
        "kind": "treePaths",
        "model": "OUT",
        "type": "Node",
        "labelFeature": "name",
        "childrenFeature": "children",
        "expected": ["/root", "/root/child"],
    },
    {
        "kind": "collectionSize",
        "model": "OUT",
        "type": "Node",
        "where": {"name": "root"},
        "path": "children",
        "expected": 1,
    },
    {
        "kind": "objects",
        "model": "OUT",
        "type": "Node",
        "features": ["name", "value"],
        "expected": [{"name": "root", "value": 1}],
    },
    {
        "kind": "referencePairs",
        "model": "OUT",
        "type": "Edge",
        "source": "source.name",
        "target": "target.name",
        "expected": [{"source": "first", "target": "second"}],
    },
)

EXPECTED_LINES = (
    '        assertEquals(2, allOfType(model0, "Node").size(), "count assertion for OUT::Node");',
    '        assertEquals(counts(list("first", "second")), counts(pathValues(model0, "Node", "name")), "featureValues assertion for OUT::Node");',
    '        assertContainsCounts(list("root"), pathValues(model0, "Node", "parent.name"), "pathValues assertion for OUT::Node");',
    '        assertEquals(counts(list("/root", "/root/child")), counts(treePaths(model0, "Node", "name", "children")), "treePaths assertion for OUT::Node");',
    '        assertCollectionSize(model0, "Node", new String[] {"name"}, "name=root", "children", 1, "collectionSize assertion for OUT::Node");',
    '        assertEquals(counts(list("name=root|value=1")), counts(signaturesOf(model0, "Node", new String[] {"name", "value"})), "objects assertion for OUT::Node");',
    '        assertEquals(counts(list("first->second")), counts(referencePairs(model0, "Edge", "source.name", "target.name")), "referencePairs assertion for OUT::Edge");',
)


class JavaAssertionRenderingTests(unittest.TestCase):
    def test_all_supported_kinds_preserve_exact_java_output(self) -> None:
        model_variables = {"OUT": "model0"}

        shared_lines = render_assertions(list(ASSERTIONS), model_variables)
        etl_lines = [
            line
            for assertion in ASSERTIONS
            for line in render_assertion(assertion, model_variables)
        ]

        self.assertEqual(list(EXPECTED_LINES), shared_lines)
        self.assertEqual(list(EXPECTED_LINES), etl_lines)

    def test_each_renderer_preserves_its_unsupported_kind_exception(self) -> None:
        assertion = {"kind": "unknown", "model": "OUT", "type": "Node"}
        renderers: tuple[
            tuple[Callable[[dict[str, Any]], list[str]], type[BaseException], str],
            ...,
        ] = (
            (
                lambda value: render_assertions([value], {"OUT": "model0"}),
                ValueError,
                "unsupported assertion kind: unknown",
            ),
            (
                lambda value: render_assertion(value, {"OUT": "model0"}),
                AssertionError,
                "Unsupported assertion kind: unknown",
            ),
        )

        for renderer, exception_type, message in renderers:
            with self.subTest(exception_type=exception_type):
                with self.assertRaisesRegex(exception_type, message):
                    renderer(assertion)

    def test_etl_renderer_preserves_unhashable_kind_exception(self) -> None:
        assertion = {"kind": [], "model": "OUT", "type": "Node"}

        with self.assertRaisesRegex(TypeError, "unhashable type: 'list'"):
            render_assertion(assertion, {"OUT": "model0"})


if __name__ == "__main__":
    unittest.main()
