"""Characterize deterministic Java assertion dispatch for every supported kind."""

from __future__ import annotations

import unittest
from typing import Any, Callable

from llm4mtl.languages.java_assertions import helpers, render_assertions
from llm4mtl.languages.etl.rendering import java_helpers, render_assertion


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


class MultiValuedPathResolutionTests(unittest.TestCase):

    RENDERERS = {"shared": helpers, "etl": java_helpers}

    def method(self, source: list[str], signature: str) -> str:
        start = next(
            index for index, line in enumerate(source) if signature in line
        )
        end = next(
            index
            for index in range(start + 1, len(source))
            if source[index] == "    }"
        )
        return "\n".join(source[start : end + 1])

    def test_a_path_segment_resolves_through_a_multi_valued_reference(self) -> None:
        for name, renderer in self.RENDERERS.items():
            with self.subTest(renderer=name):
                rendered = self.method(
                    renderer(), "private Object pathValue(Object object, String path)"
                )
                self.assertIn("current instanceof Collection<?>", rendered)
                self.assertIn("featureValue(element, part)", rendered)

    def test_a_resolved_collection_renders_its_elements(self) -> None:
        for name, renderer in self.RENDERERS.items():
            with self.subTest(renderer=name):
                rendered = self.method(
                    renderer(), "private String stringValue(Object value)"
                )
                self.assertIn("value instanceof Collection<?>", rendered)
                self.assertIn('String.join(",", rendered)', rendered)

    def test_string_value_renders_null_and_references_alike(self) -> None:
        """Both harnesses print an unset value as "null" and a reference by identity."""
        for name, renderer in self.RENDERERS.items():
            with self.subTest(renderer=name):
                rendered = self.method(
                    renderer(), "private String stringValue(Object value)"
                )
                self.assertIn('return "null";', rendered)
                self.assertIn('new String[] {"name", "label", "id", "value"}', rendered)

    def test_path_values_keep_an_unset_terminal_value_as_null(self) -> None:
        """``eOperations.name`` of a nameless operation is observed as "null".

        The harness stringifies null as "null"; dropping it made ``[null]``
        impossible to assert, while an intermediate null (no parent at all)
        still contributes nothing.
        """
        for name, renderer in self.RENDERERS.items():
            with self.subTest(renderer=name):
                source = renderer()
                path_values = self.method(source, "pathValues(")
                self.assertIn("pathValuesFrom(object, path, true)", path_values)
                resolver = self.method(
                    source, "pathValuesFrom(Object object, String path, boolean keepTerminalNull)"
                )
                self.assertIn("if (next == null && keepTerminalNull)", resolver)
                self.assertIn("values.add(null)", resolver)
                self.assertIn("pathValuesFrom(next, rest, keepTerminalNull)", resolver)


class ExpectedValueRenderingTests(unittest.TestCase):
    """JSON booleans and nulls are written the way the harness prints them."""

    MODEL_VARIABLES = {"OUT": "model0"}

    def render(self, assertion: dict[str, Any]) -> list[str]:
        shared = render_assertions([assertion], self.MODEL_VARIABLES)
        etl = render_assertion(assertion, self.MODEL_VARIABLES)
        self.assertEqual(shared, etl)
        return shared

    def test_boolean_and_null_object_features_match_java_rendering(self) -> None:
        lines = self.render(
            {
                "kind": "objects",
                "model": "OUT",
                "type": "Product",
                "features": ["name", "inStock", "note"],
                "expected": [{"name": "Mug", "inStock": True, "note": None}],
            }
        )
        self.assertIn('list("name=Mug|inStock=true|note=null")', lines[0])
        self.assertNotIn("True", lines[0])
        self.assertNotIn("None", lines[0])

    def test_boolean_and_null_path_values_match_java_rendering(self) -> None:
        lines = self.render(
            {
                "kind": "pathValues",
                "model": "OUT",
                "type": "EClass",
                "path": "eOperations.name",
                "expected": [None, False, 3],
            }
        )
        self.assertIn('list("null", "false", "3")', lines[0])
