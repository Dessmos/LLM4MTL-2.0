"""What executing a transformation produced, as one canonical vocabulary.

Every language reports failure in its own dialect. Normalising those into one
taxonomy at the adapter boundary is what lets a single comparator and a single
set of metrics work across all four languages — and it keeps the distinctions
that matter scientifically: a transformation that failed to parse, one that ran
and produced nothing, and one that ran and produced the wrong thing are three
different observations, not one "failure".

Success carries a snapshot per model slot rather than a single target model,
because Reactions propagates into several related models at once and ETL tasks
can have multiple targets.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OutcomeStatus(str, Enum):
    """The canonical result of executing a transformation on one scenario."""

    SUCCESS = "success"
    PARSE_FAILED = "parse_failed"
    COMPILE_FAILED = "compile_failed"
    RUNTIME_FAILED = "runtime_failed"
    EMPTY_OUTPUT = "empty_output"
    TIMED_OUT = "timed_out"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"

    @property
    def is_success(self) -> bool:
        return self is OutcomeStatus.SUCCESS

    @property
    def is_attributable_to_the_transformation(self) -> bool:
        """Whether this outcome says something about the transformation itself.

        Infrastructure failures and timeouts do not: they say the experiment
        could not observe the transformation, which must stay distinguishable
        from observing that it misbehaved.
        """
        return self not in {OutcomeStatus.INFRASTRUCTURE_FAILED, OutcomeStatus.TIMED_OUT}


@dataclass(frozen=True)
class ModelSnapshot:
    """The state of one model slot after execution.

    ``content_hash`` identifies the produced state; semantic comparison of two
    snapshots is the comparator's job and deliberately not a byte comparison.
    """

    slot: str
    path: str
    content_hash: str


@dataclass(frozen=True)
class TransformationOutcome:
    """The normalized result of running one scenario against one transformation."""

    status: OutcomeStatus
    snapshots: tuple[ModelSnapshot, ...] = ()
    diagnostic: str = ""

    def __post_init__(self) -> None:
        if self.status.is_success and not self.snapshots:
            raise ValueError("a successful outcome must carry at least one model snapshot")
        if not self.status.is_success and self.snapshots:
            raise ValueError(
                f"a {self.status.value} outcome cannot carry model snapshots"
            )

    @property
    def is_success(self) -> bool:
        return self.status.is_success

    def snapshot_for(self, slot: str) -> ModelSnapshot:
        for snapshot in self.snapshots:
            if snapshot.slot == slot:
                return snapshot
        raise KeyError(f"no snapshot for slot '{slot}'")

    @property
    def slots(self) -> tuple[str, ...]:
        return tuple(snapshot.slot for snapshot in self.snapshots)
