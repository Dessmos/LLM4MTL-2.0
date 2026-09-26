"""Boundary cases of the Java class name the renderer gives a generated suite."""

from __future__ import annotations

import unittest

from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_class_name


class SanitizeClassNameTests(unittest.TestCase):

    def test_usable_names_keep_their_simple_class_name(self) -> None:
        cases = (
            ("SmokeSemanticTest", "SmokeSemanticTest"),
            ("Foo.java", "Foo"),
            ("org.example.FooTest", "FooTest"),
            ("org.example.FooTest.java", "FooTest"),
            ("Foo-Bar Test", "FooBarTest"),
            ("_Private", "_Private"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(expected, sanitize_class_name(value, "Tree2Graph"))

    def test_unusable_names_fall_back_to_the_task_name(self) -> None:
        for value in ("", "1Test", "---", ".java", "org.example."):
            with self.subTest(value=value):
                self.assertEqual(
                    "GeneratedTree2GraphSemanticTest",
                    sanitize_class_name(value, "Tree2Graph"),
                )

    def test_the_fallback_does_not_depend_on_a_language(self) -> None:
        for task in ("", "42"):
            with self.subTest(task=task):
                self.assertEqual(
                    "GeneratedSemanticTest", sanitize_class_name("", task)
                )


if __name__ == "__main__":
    unittest.main()
