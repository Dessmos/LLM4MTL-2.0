from __future__ import annotations

import json
import unittest

from llm4mtl.conventions import LANGUAGE_CONFIGS, default_task_contracts_root
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
    resolve_custom_task_inputs,
    resolve_task_inputs,
)


class PromptInputResolutionTests(unittest.TestCase):

    def test_every_task_resolves_only_contract_named_metamodels(self) -> None:
        for language, config in LANGUAGE_CONFIGS.items():
            contracts_root = default_task_contracts_root(config)
            for contract_path in sorted(contracts_root.glob("*.json")):
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                expected = []
                for model in contract["models"]:
                    path = model.get("metamodelFile")
                    if path and path not in expected:
                        expected.append(path)

                with self.subTest(language=language, task=contract_path.stem):
                    resolved = resolve_task_inputs(language, contract_path.stem)
                    self.assertEqual(
                        expected,
                        [metamodel.path for metamodel in resolved.metamodels],
                    )
                    self.assertEqual(contract["reference"], resolved.reference.path)
                    self.assertEqual(contract_path.stem, resolved.task)
                    self.assertTrue(resolved.reference.content)
                    self.assertTrue(resolved.grammar.content)
                    for metamodel in resolved.metamodels:
                        self.assertTrue(metamodel.content)
                        self.assertTrue(
                            (REPO_ROOT / metamodel.path).is_relative_to(
                                TARGET.benchmark / "metamodels"
                            )
                        )

    def test_tree2graph_does_not_receive_unrelated_etl_metamodels(self) -> None:
        resolved = resolve_task_inputs("etl", "Tree2Graph")
        self.assertEqual(
            [
                "benchmark/metamodels/additional_models/ETL_model/Graph.ecore",
                "benchmark/metamodels/additional_models/ETL_model/Tree.ecore",
            ],
            [metamodel.path for metamodel in resolved.metamodels],
        )
        self.assertNotIn("Flowchart.ecore", resolved.metamodel_text)
        self.assertNotIn("HTML.ecore", resolved.metamodel_text)

    def test_task_without_external_metamodel_file_resolves_an_empty_set(self) -> None:
        # rss2atom is plain XML on both sides, so no metamodel file exists to
        # supply. Every task whose contract does name metamodel files receives
        # them, in every language.
        resolved = resolve_task_inputs("etl", "rss2atom")
        self.assertEqual((), resolved.metamodels)
        self.assertEqual("", resolved.metamodel_text)

    def test_qvto_receives_the_ecore_metamodel_its_contract_names(self) -> None:
        resolved = resolve_task_inputs("qvto", "Constructors")
        self.assertEqual(
            ["benchmark/metamodels/additional_models/QVT-O_model/Ecore.ecore"],
            [metamodel.path for metamodel in resolved.metamodels],
        )
        self.assertIn("EClassifier", resolved.metamodel_text)

    def test_invalid_or_unknown_task_fails_without_fallback(self) -> None:
        for task in ("../Tree2Graph", "does-not-exist"):
            with self.subTest(task=task):
                with self.assertRaises(TaskInputResolutionError):
                    resolve_task_inputs("etl", task)


class CustomTaskInputResolutionTests(unittest.TestCase):
    """What a task resolves to when the user supplied its metamodel.

    The prompts read the same fields either way, so the difference has to be in
    what those fields hold: the user's metamodel, this language's grammar, and
    nothing selected through a contract the task does not have.
    """

    METAMODEL = "class Tree { children: Tree[] }"

    def test_the_supplied_metamodel_is_the_only_one_resolved(self) -> None:
        resolved = resolve_custom_task_inputs("etl", "TreeFlattening", self.METAMODEL)
        self.assertEqual(
            ["custom-task-metamodel"],
            [metamodel.path for metamodel in resolved.metamodels],
        )
        self.assertIn(self.METAMODEL, resolved.metamodel_text)
        self.assertEqual("TreeFlattening", resolved.task)
        self.assertEqual("etl", resolved.language)

    def test_no_benchmark_input_reaches_a_custom_task(self) -> None:
        resolved = resolve_custom_task_inputs("etl", "TreeFlattening", self.METAMODEL)
        # A reference would be the answer, a contract would name another task's
        # metamodels, and its URIs would name namespaces this metamodel has not.
        self.assertIsNone(resolved.reference)
        self.assertIsNone(resolved.contract_path)
        self.assertEqual((), resolved.metamodel_uris)
        self.assertEqual("", resolved.metamodel_uri_text)
        self.assertEqual((), resolved.prerequisite_prompts)
        self.assertNotIn("Tree2Graph", resolved.metamodel_text)

    def test_the_grammar_is_the_language_s_as_for_any_task(self) -> None:
        for language in LANGUAGE_CONFIGS:
            with self.subTest(language=language):
                resolved = resolve_custom_task_inputs(
                    language, "MyTask", self.METAMODEL
                )
                self.assertTrue(resolved.grammar.content)
                self.assertEqual(
                    resolve_task_inputs(
                        language, _any_task(language)
                    ).grammar.path,
                    resolved.grammar.path,
                )

    def test_an_unsafe_name_empty_metamodel_or_unknown_language_is_refused(
        self,
    ) -> None:
        cases = {
            "unsafe task name": ("etl", "../escape", self.METAMODEL),
            "empty metamodel": ("etl", "TreeFlattening", "   "),
            "unknown language": ("nope", "TreeFlattening", self.METAMODEL),
        }
        for label, (language, task, metamodel) in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(TaskInputResolutionError):
                    resolve_custom_task_inputs(language, task, metamodel)


def _any_task(language: str) -> str:
    contracts = default_task_contracts_root(LANGUAGE_CONFIGS[language])
    return sorted(contracts.glob("*.json"))[0].stem


if __name__ == "__main__":
    unittest.main()
