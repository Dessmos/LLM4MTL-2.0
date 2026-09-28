"""Can the shared contract express all four languages' semantics?

The contract is only validated once a language that is NOT a batch model-to-model
transformation fits it without special-casing. The Reactions case below is
transcribed from a real reference,
`FamiliesToPersons_InsertedDaughter.reactions`, which reacts to
`families::Member inserted in families::Family[daughters]` by creating a
`persons::Female` whose `fullName` combines the member's first name and the
family's last name.

If these tests need a Reactions-only field added to the shared types, the shared
abstraction was derived from ETL and is wrong.
"""

from __future__ import annotations

import unittest

from llm4mtl.domain import (
    ChangeKind,
    ChangeOperation,
    ElementRef,
    ElementSpec,
    Expectation,
    ModelRole,
    ModelSlot,
    ScenarioKind,
    SemanticScenario,
    SemanticSuite,
)

FAMILIES = "http://vitruv.tools/methodologisttemplate/families"
PERSONS = "http://vitruv.tools/methodologisttemplate/persons"


def inserted_daughter_scenario() -> SemanticScenario:
    """The real FamiliesToPersons_InsertedDaughter reaction, as a scenario."""
    return SemanticScenario(
        name="insertingADaughterCreatesAFemale",
        kind=ScenarioKind.CHANGE_PROPAGATION,
        slots=(
            ModelSlot(
                name="families",
                role=ModelRole.INOUT,
                metamodel=FAMILIES,
                artifact="models/families.xmi",
            ),
            ModelSlot(
                name="persons",
                role=ModelRole.INOUT,
                metamodel=PERSONS,
                artifact="models/persons.xmi",
            ),
        ),
        changes=(
            ChangeOperation(
                kind=ChangeKind.ADD_TO_COLLECTION,
                target=ElementRef(
                    slot="families", type_name="Family", where={"lastName": "Smith"}
                ),
                feature="daughters",
                value=ElementSpec(type_name="Member", features={"firstName": "Anna"}),
            ),
        ),
        expectations=(
            Expectation(
                kind="count",
                slot="persons",
                type_name="Female",
                payload={"expected": 1},
            ),
            Expectation(
                kind="feature_values",
                slot="persons",
                type_name="Female",
                payload={"feature": "fullName", "expected": ["Anna Smith"]},
            ),
        ),
    )


class ChangePropagationTests(unittest.TestCase):

    def test_both_related_models_are_read_and_written(self) -> None:
        # Reactions needs slots that are simultaneously input and output; a
        # source/target pair inherited from ETL could not express this.
        scenario = inserted_daughter_scenario()
        for name in ("families", "persons"):
            slot = _slot(scenario, name)
            self.assertTrue(slot.role.is_readable, name)
            self.assertIs(ModelRole.INOUT, slot.role, name)

    def test_a_change_scenario_must_declare_a_change(self) -> None:
        with self.assertRaises(ValueError):
            SemanticScenario(
                name="noChange",
                kind=ScenarioKind.CHANGE_PROPAGATION,
                slots=(
                    ModelSlot("families", ModelRole.INOUT, FAMILIES, "models/f.xmi"),
                ),
                expectations=(
                    Expectation("count", "families", "Family", {"expected": 1}),
                ),
            )


class BatchTransformationTests(unittest.TestCase):

    def test_a_batch_scenario_cannot_declare_changes(self) -> None:
        with self.assertRaises(ValueError):
            SemanticScenario(
                name="batchWithChange",
                kind=ScenarioKind.BATCH_TRANSFORMATION,
                slots=(
                    ModelSlot("source", ModelRole.INPUT, "Tree", "models/in.model"),
                ),
                expectations=(Expectation("count", "source", "Tree", {"expected": 1}),),
                changes=(
                    ChangeOperation(
                        kind=ChangeKind.DELETE,
                        target=ElementRef(slot="source", type_name="Tree"),
                    ),
                ),
            )

    def test_a_read_slot_needs_an_initial_artifact(self) -> None:
        with self.assertRaises(ValueError):
            ModelSlot(name="source", role=ModelRole.INPUT, metamodel="Tree")


class ScenarioIntegrityTests(unittest.TestCase):

    def test_expectations_must_name_a_declared_slot(self) -> None:
        with self.assertRaises(ValueError):
            SemanticScenario(
                name="strayExpectation",
                kind=ScenarioKind.BATCH_TRANSFORMATION,
                slots=(
                    ModelSlot("source", ModelRole.INPUT, "Tree", "models/in.model"),
                ),
                expectations=(
                    Expectation("count", "elsewhere", "Node", {"expected": 1}),
                ),
            )

    def test_both_kinds_live_in_one_suite(self) -> None:
        suite = SemanticSuite(
            suite_id="suite_001",
            language="reactions",
            task="FamiliesToPersons",
            scenarios=(inserted_daughter_scenario(),),
        )
        self.assertEqual(1, len(suite.scenarios))

        with self.assertRaises(ValueError):
            SemanticSuite(
                suite_id="empty", language="etl", task="Tree2Graph", scenarios=()
            )


def _slot(scenario, name: str):
    """The scenario's model slot called ``name``."""
    return next(slot for slot in scenario.slots if slot.name == name)


if __name__ == "__main__":
    unittest.main()
