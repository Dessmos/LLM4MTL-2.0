"""Invariants of the canonical transformation outcome.

The taxonomy exists so that "the transformation misbehaved" and "the experiment
could not observe the transformation" never collapse into one number.
"""

from __future__ import annotations

import unittest

from llm4mtl.domain import OutcomeStatus


class OutcomeTests(unittest.TestCase):

    def test_unobserved_runs_stay_distinguishable_from_misbehaviour(self) -> None:
        # A timeout or a broken harness says nothing about the transformation and
        # must never be counted as evidence that it behaved wrongly.
        for status in (OutcomeStatus.TIMED_OUT, OutcomeStatus.INFRASTRUCTURE_FAILED):
            with self.subTest(status=status):
                self.assertFalse(status.is_attributable_to_the_transformation)

        for status in (
            OutcomeStatus.PARSE_FAILED,
            OutcomeStatus.COMPILE_FAILED,
            OutcomeStatus.RUNTIME_FAILED,
        ):
            with self.subTest(status=status):
                self.assertTrue(status.is_attributable_to_the_transformation)


if __name__ == "__main__":
    unittest.main()
