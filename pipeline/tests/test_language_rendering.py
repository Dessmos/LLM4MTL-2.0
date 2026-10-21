"""Behavior locks for language-specific deterministic Java rendering."""

from __future__ import annotations

import unittest

from llm4mtl.languages.atl.rendering import render_atl_test
from llm4mtl.languages.etl.rendering import model_resource_path
from llm4mtl.languages.qvto.rendering import _render_method as render_qvto_method
from llm4mtl.languages.reactions.rendering import _java_value, _render_change

ATL_SPEC = {
    "transformation": "transformations/Families2Persons.atl",
    "models": [
        {
            "name": "IN",
            "role": "source",
            "path": "models\\members.xmi",
            "metamodelFile": "metamodels/Families.ecore",
            "metamodelUri": "http://families",
            "metamodelAlias": "Families",
        },
        {"name": "OUT", "role": "target", "metamodelUri": "http://persons"},
    ],
    "tests": [
        {
            "name": "maps every member",
            "assertions": [
                {"kind": "count", "model": "OUT", "type": "Person", "expected": 2}
            ],
        }
    ],
}


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


class AtlRenderingTests(unittest.TestCase):

    def test_class_holds_the_setup_one_method_per_case_and_the_helpers(
        self,
    ) -> None:
        rendered = render_atl_test("Families2PersonsTest", ATL_SPEC, "Families2Persons")
        lines = rendered.split("\n")

        self.assertEqual("package org.example.generated;", lines[0])
        self.assertIn("public class Families2PersonsTest {", lines)
        self.assertEqual(1, rendered.count("    @Test"))
        self.assertIn("    void mapsEveryMember() throws Exception {", lines)
        for helper in ("loadModel", "executeAtl", "compileAtl", "writeSnapshot"):
            with self.subTest(helper=helper):
                self.assertRegex(rendered, rf"private \S+ {helper}\(")
        self.assertEqual(["}", ""], lines[-2:])

    def test_method_loads_the_source_runs_the_module_and_asserts_the_target(
        self,
    ) -> None:
        rendered = render_atl_test("Families2PersonsTest", ATL_SPEC, "Families2Persons")

        self.assertIn(
            'Resource source = loadModel("generated-models/families2persons/members.xmi", '
            '"Families.ecore", "http://families");',
            rendered,
        )
        self.assertIn(
            'List<EObject> targetRoots = executeAtl("Families2Persons.atl", source, '
            '"Families.ecore", "OUT.ecore", "Families", "OUT", "http://persons");',
            rendered,
        )
        self.assertIn('writeSnapshot("mapsEveryMember/OUT.xmi", targetRoots);', rendered)
        self.assertIn('allOfType(targetRoots, "Person").size()', rendered)

    def test_a_case_without_exactly_one_source_and_target_is_refused(self) -> None:
        spec = {**ATL_SPEC, "models": ATL_SPEC["models"][:1]}

        with self.assertRaisesRegex(ValueError, "needs exactly one source and target"):
            render_atl_test("Families2PersonsTest", spec, "Families2Persons")


class EtlModelResourcePathTests(unittest.TestCase):

    def test_generated_models_live_under_the_task_folder(self) -> None:
        cases = (
            ("models/input.xmi", "generated-models/tree2graph/input.xmi"),
            ("/models/input.xmi", "generated-models/tree2graph/input.xmi"),
            ("models\\nested\\input.xmi", "generated-models/tree2graph/nested/input.xmi"),
            ("input.xmi", "generated-models/tree2graph/input.xmi"),
        )
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(expected, model_resource_path(path, "Tree2Graph", True))

    def test_other_models_keep_their_classpath_path(self) -> None:
        cases = (
            ("models/input.xmi", "models/input.xmi"),
            ("/fixtures\\input.xmi", "fixtures/input.xmi"),
        )
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(expected, model_resource_path(path, "Tree2Graph", False))


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
                    _java_value(value, slot_uris, "default-uri"),
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
            _java_value([], {}, "uri")
        with self.assertRaisesRegex(ValueError, "a created element needs a type"):
            _java_value({}, {}, "uri")
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
