"""Language-neutral description of one semantic test.

The four supported languages do not share an execution model. ETL, ATL and
QVT-O are batch transformations::

    input model state -> transformation -> output model state

Reactions propagates change between already-related models::

    related model states -> declared change -> reaction -> propagated states

A representation derived only from the batch languages cannot express the second
shape, so both scenario kinds are part of the contract from the start. Named
model slots (rather than a fixed source/target pair) are what makes this work:
Reactions needs `families` and `persons` to be first-class and simultaneously
readable and writable, and multi-target ETL tasks need more than one output.

Changes are a closed vocabulary of operations over slots and features. The LLM
never authors executable change code — the adapter renders these deterministically,
exactly as it renders assertions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ScenarioKind(str, Enum):
    """How the transformation under test is exercised."""

    BATCH_TRANSFORMATION = "batch_transformation"
    CHANGE_PROPAGATION = "change_propagation"


class ModelRole(str, Enum):
    """What the scenario does with a model slot.

    ``INOUT`` exists for change propagation, where a model is both an input the
    reaction reads and a state the reaction updates.
    """

    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"

    @property
    def is_readable(self) -> bool:
        return self is not ModelRole.OUTPUT

    @property
    def is_written(self) -> bool:
        return self is not ModelRole.INPUT


class ChangeKind(str, Enum):
    """The closed set of model changes a scenario may declare."""

    CREATE = "create"
    DELETE = "delete"
    SET_FEATURE = "set_feature"
    ADD_TO_COLLECTION = "add_to_collection"
    REMOVE_FROM_COLLECTION = "remove_from_collection"
    MOVE = "move"


@dataclass(frozen=True)
class ModelSlot:
    """One named model a scenario reads, writes, or both."""

    name: str
    role: ModelRole
    metamodel: str
    artifact: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a model slot needs a name")
        if self.role.is_readable and not self.artifact:
            raise ValueError(
                f"model slot '{self.name}' is read by the scenario but declares no initial artifact"
            )


@dataclass(frozen=True)
class ElementSpec:
    """A model element to be created, described by type and feature values."""

    type_name: str
    features: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ElementRef:
    """A model element selected by type and feature values within one slot."""

    slot: str
    type_name: str
    where: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChangeOperation:
    """One declared change applied before the transformation reacts."""

    kind: ChangeKind
    target: ElementRef
    feature: str | None = None
    value: ElementSpec | ElementRef | str | int | float | bool | None = None

    def __post_init__(self) -> None:
        needs_feature = {
            ChangeKind.SET_FEATURE,
            ChangeKind.ADD_TO_COLLECTION,
            ChangeKind.REMOVE_FROM_COLLECTION,
            ChangeKind.MOVE,
        }
        if self.kind in needs_feature and not self.feature:
            raise ValueError(f"{self.kind.value} needs the feature it changes")
        if self.kind is ChangeKind.DELETE and self.value is not None:
            raise ValueError("delete does not take a value")
        if self.kind in {ChangeKind.CREATE, ChangeKind.ADD_TO_COLLECTION} and self.value is None:
            raise ValueError(f"{self.kind.value} needs the element it adds")


@dataclass(frozen=True)
class Expectation:
    """One observable fact asserted about a slot after execution.

    ``kind`` and ``payload`` stay open on purpose: the vocabulary of observable
    facts (counts, feature values, reference pairs) is shared across languages
    because all four are EMF-based, while turning a fact into an executable
    check is the adapter's job.
    """

    kind: str
    slot: str
    type_name: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.kind or not self.slot or not self.type_name:
            raise ValueError("an expectation needs a kind, a slot, and a type")


@dataclass(frozen=True)
class SemanticScenario:
    """One executable semantic test case, independent of language."""

    name: str
    kind: ScenarioKind
    slots: tuple[ModelSlot, ...]
    expectations: tuple[Expectation, ...]
    changes: tuple[ChangeOperation, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a scenario needs a name")
        if not self.slots:
            raise ValueError(f"scenario '{self.name}' declares no model slots")
        if not self.expectations:
            raise ValueError(f"scenario '{self.name}' asserts nothing")

        slot_names = {slot.name for slot in self.slots}
        if len(slot_names) != len(self.slots):
            raise ValueError(f"scenario '{self.name}' declares duplicate slot names")
        for expectation in self.expectations:
            if expectation.slot not in slot_names:
                raise ValueError(
                    f"scenario '{self.name}' asserts on unknown slot '{expectation.slot}'"
                )
        for change in self.changes:
            if change.target.slot not in slot_names:
                raise ValueError(
                    f"scenario '{self.name}' changes unknown slot '{change.target.slot}'"
                )

        if self.kind is ScenarioKind.CHANGE_PROPAGATION and not self.changes:
            raise ValueError(
                f"scenario '{self.name}' propagates change but declares none"
            )
        if self.kind is ScenarioKind.BATCH_TRANSFORMATION and self.changes:
            raise ValueError(
                f"scenario '{self.name}' is a batch transformation and cannot declare changes"
            )

    def slot(self, name: str) -> ModelSlot:
        for slot in self.slots:
            if slot.name == name:
                return slot
        raise KeyError(f"scenario '{self.name}' has no slot '{name}'")


@dataclass(frozen=True)
class SemanticSuite:
    """The generated semantic tests of one suite, for one language and task."""

    suite_id: str
    language: str
    task: str
    scenarios: tuple[SemanticScenario, ...]

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValueError(f"suite '{self.suite_id}' contains no scenarios")
        names = [scenario.name for scenario in self.scenarios]
        if len(set(names)) != len(names):
            raise ValueError(f"suite '{self.suite_id}' contains duplicate scenario names")
