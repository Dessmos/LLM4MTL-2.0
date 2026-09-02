"""Behavior locks for language-specific deterministic Java rendering."""

from __future__ import annotations

import unittest

from llm4mtl.languages.qvto.rendering import _render_method as render_qvto_method
from llm4mtl.languages.reactions.rendering import _java_value, _render_change


class QvtoRenderingTests(unittest.TestCase):

    def test_single_output_method_preserves_paths_variables_and_assertions(
        self,
    ) -> None:
        spec = {
            "transformation": "transformations/Tree2Graph.qvto",
            "models": [
                {
                    "name": "IN",
                    "role": "source",
                    "path": "models/input.xmi",
                },
                {"name": "OUT", "role": "target"},
            ],
        }
        test = {
            "name": "maps roots",
            "assertions": [
                {
                    "kind": "count",
                    "model": "OUT",
                    "type": "Node",
                    "expected": 2,
                }
            ],
        }

        rendered = render_qvto_method(spec, test, "Tree2Graph")

        self.assertIn(
            'BasicModelExtent input = loadInputModel("generated-models/tree2graph/input.xmi");',
            rendered,
        )
        self.assertIn(
            'BasicModelExtent output = executeTransformation("Tree2Graph.qvto", input);',
            rendered,
        )
        self.assertIn('writeSnapshot("mapsRoots/OUT.xmi", target0Roots);', rendered)
        self.assertIn('allOfType(target0Roots, "Node").size()', rendered)

    def test_invalid_source_target_cardinality_keeps_its_error(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "needs one source and one or two targets",
        ):
            render_qvto_method(
                {"transformation": "example.qvto", "models": []},
                {"name": "invalid", "assertions": []},
                "Example",
            )


class ReactionsRenderingTests(unittest.TestCase):

    def test_java_values_preserve_scalar_reference_and_created_object_forms(
        self,
    ) -> None:
        slot_uris = {"families": "families-uri"}
        cases = (
            (None, "null"),
            (True, "Boolean.TRUE"),
            (3, "3"),
            ("Ada", '"Ada"'),
            (
                {
                    "slot": "families",
                    "type": "Family",
                    "where": {"name": "Smith"},
                },
                'find(view, "families-uri", "Family", map("name", "Smith"))',
            ),
            (
                {"type": "Family", "features": {"name": "Smith"}},
                'createObject("default-uri", "Family", map("name", "Smith"))',
            ),
        )

        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(
                    expected,
                    _java_value(value, slot_uris, "view", "default-uri"),
                )

    def test_change_dispatch_preserves_each_operation_name(self) -> None:
        slot_uris = {"families": "families-uri"}
        target = {
            "slot": "families",
            "type": "Family",
            "where": {"name": "Smith"},
        }
        operations = {
            "set_feature": "setFeature",
            "add_to_collection": "addToCollection",
            "remove_from_collection": "removeFromCollection",
            "move": "moveInto",
        }

        for kind, operation in operations.items():
            with self.subTest(kind=kind):
                rendered = _render_change(
                    {
                        "kind": kind,
                        "target": target,
                        "feature": "members",
                        "value": "Ada",
                    },
                    slot_uris,
                    0,
                )
                self.assertIn(f"{operation}(find(view", rendered[1])
                self.assertIn(', "members", "Ada");', rendered[1])

    def test_create_and_delete_keep_their_special_rendering(self) -> None:
        slot_uris = {"families": "families-uri"}
        target = {
            "slot": "families",
            "type": "Family",
            "where": {"name": "Smith"},
        }

        deleted = _render_change(
            {"kind": "delete", "target": target},
            slot_uris,
            0,
        )
        created = _render_change(
            {
                "kind": "create",
                "target": target,
                "value": {"type": "Family"},
            },
            slot_uris,
            2,
        )

        self.assertIn("EcoreUtil.delete(find(view", deleted[1])
        self.assertIn("EObject created2 = createObject", created[1])
        self.assertIn('resolve("created-2.xmi")', created[2])

    def test_unsupported_value_and_change_errors_are_preserved(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported declarative change value"):
            _java_value([], {}, "view", "uri")
        with self.assertRaisesRegex(ValueError, "a created element needs a type"):
            _java_value({}, {}, "view", "uri")
        with self.assertRaisesRegex(ValueError, "unsupported Reactions change kind"):
            _render_change(
                {
                    "kind": "unknown",
                    "target": {"slot": "model", "type": "Root"},
                },
                {"model": "uri"},
                0,
            )


if __name__ == "__main__":
    unittest.main()
