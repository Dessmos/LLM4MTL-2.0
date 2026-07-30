from __future__ import annotations

import json
import unittest

from llm4mtl.conventions import LANGUAGE_CONFIGS, default_task_contracts_root
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
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
                "benchmark/metamodels/etl/Graph.ecore",
                "benchmark/metamodels/etl/Tree.ecore",
            ],
            [metamodel.path for metamodel in resolved.metamodels],
        )
        self.assertNotIn("Flowchart.ecore", resolved.metamodel_text)
        self.assertNotIn("HTML.ecore", resolved.metamodel_text)

    def test_task_without_external_metamodel_file_resolves_an_empty_set(self) -> None:
        resolved = resolve_task_inputs("qvto", "Constructors")
        self.assertEqual((), resolved.metamodels)
        self.assertEqual("", resolved.metamodel_text)

    def test_invalid_or_unknown_task_fails_without_fallback(self) -> None:
        for task in ("../Tree2Graph", "does-not-exist"):
            with self.subTest(task=task):
                with self.assertRaises(TaskInputResolutionError):
                    resolve_task_inputs("etl", task)


if __name__ == "__main__":
    unittest.main()
