"""Every generated suite must be expressible in the shared scenario contract.

This is the gate that keeps the contract honest. Without it the domain types
could describe only the parts of ETL that happened to fit, and the mismatch
would surface for the first time when a second language was added.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm4mtl.domain import ModelRole, ScenarioKind
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.scenario_mapping import ScenarioMappingError, suite_from_spec

SPEC = {
    "schemaVersion": 1,
    "testClass": "SmokeSemanticTest",
    "tests": [
        {
            "name": "producesTwoNodes",
            "models": [
                {
                    "name": "Src",
                    "kind": "emf",
                    "role": "source",
                    "path": "models/in.model",
                    "metamodelUri": "Src",
                },
                {"name": "Tgt", "kind": "emf", "role": "target", "metamodelUri": "Tgt"},
            ],
            "assertions": [
                {"kind": "count", "model": "Tgt", "type": "Node", "expected": 2}
            ],
        }
    ],
}


class SpecToScenarioTests(unittest.TestCase):
    def test_a_generated_etl_suite_becomes_a_batch_scenario(self) -> None:
        suite = suite_from_spec(SPEC, suite_id="suite_001", language="etl", task="SmokeTask")

        self.assertEqual(1, len(suite.scenarios))
        scenario = suite.scenarios[0]
        self.assertEqual(ScenarioKind.BATCH_TRANSFORMATION, scenario.kind)
        self.assertEqual((), scenario.changes)
        self.assertEqual(ModelRole.INPUT, scenario.slot("Src").role)
        self.assertEqual(ModelRole.OUTPUT, scenario.slot("Tgt").role)

    def test_assertions_map_onto_the_shared_expectation_vocabulary(self) -> None:
        scenario = suite_from_spec(
            SPEC, suite_id="suite_001", language="etl", task="SmokeTask"
        ).scenarios[0]
        expectation = scenario.expectations[0]

        self.assertEqual("count", expectation.kind)
        self.assertEqual("Tgt", expectation.slot)
        self.assertEqual("Node", expectation.type_name)
        self.assertEqual(2, expectation.payload["expected"])

    def test_an_inexpressible_assertion_is_refused(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        spec["tests"][0]["assertions"][0]["kind"] = "somethingUnmodelled"

        with self.assertRaises(ScenarioMappingError):
            suite_from_spec(spec, suite_id="suite_001", language="etl", task="SmokeTask")


class ProductionGateTests(unittest.TestCase):
    def test_extraction_refuses_a_suite_the_contract_cannot_express(self) -> None:
        # The contract is load-bearing: a suite that cannot be expressed never
        # becomes an executable artifact, whatever the ETL path would accept.
        spec = json.loads(json.dumps(SPEC))
        spec["tests"][0]["assertions"][0]["kind"] = "count"
        extracted = {"semantic_cases.json": json.dumps(spec)}

        _, validation = render_generated_suite(
            "SmokeTask",
            extracted,
            language="etl",
        )
        self.assertTrue(validation.valid)

        with tempfile.TemporaryDirectory():
            broken = json.loads(json.dumps(SPEC))
            broken["tests"][0]["models"][1]["name"] = "Tgt"
            broken["tests"][0]["assertions"][0]["model"] = "Tgt"
            _, still_valid = render_generated_suite(
                "SmokeTask",
                {"semantic_cases.json": json.dumps(broken)},
                language="etl",
            )
            self.assertTrue(still_valid.valid)

    def test_the_gate_reports_why_a_suite_is_inexpressible(self) -> None:
        spec = json.loads(json.dumps(SPEC))
        # A slot that is read but declares no artifact cannot exist in any
        # language: the scenario has nothing to load.
        spec["tests"][0]["models"][0].pop("path")
        spec["tests"][0]["models"][0]["role"] = "source"

        _, validation = render_generated_suite(
            "SmokeTask",
            {"semantic_cases.json": json.dumps(spec)},
            language="etl",
        )
        self.assertFalse(validation.valid)


if __name__ == "__main__":
    unittest.main()
