"""Why executing a transformation failed, as one canonical vocabulary.

Every language reports failure in its own way. The language adapter maps each
report onto this one vocabulary, so one set of metrics works for all four
languages. It keeps the distinctions that matter: a transformation that failed
to parse, one that failed at run time, and a run the experiment could not
observe at all are different observations, not one "failure".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OutcomeStatus(str, Enum):
    """The canonical failure of executing a transformation on one scenario."""

    PARSE_FAILED = "parse_failed"
    COMPILE_FAILED = "compile_failed"
    RUNTIME_FAILED = "runtime_failed"
    TIMED_OUT = "timed_out"
    INFRASTRUCTURE_FAILED = "infrastructure_failed"

    @property
    def is_attributable_to_the_transformation(self) -> bool:
        """Whether this outcome says something about the transformation itself.

        Infrastructure failures and timeouts do not: they mean the experiment
        could not observe the transformation, which must stay distinct from
        observing that it misbehaved.

        Only the execution stage uses this, where the suite has already passed
        reference validation. It records what the run observed, not who is at
        fault: Source Diagnosis decides whether the transformation, the test, or
        neither should be refined.
        """
        return self not in {
            OutcomeStatus.INFRASTRUCTURE_FAILED,
            OutcomeStatus.TIMED_OUT,
        }


@dataclass(frozen=True)
class TransformationOutcome:
    """The normalized failure of running one scenario against one transformation."""

    status: OutcomeStatus
    diagnostic: str = ""
