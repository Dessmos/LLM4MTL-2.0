"""Invariants of the canonical transformation outcome.

The taxonomy exists so that "the transformation misbehaved" and "the experiment
could not observe the transformation" never collapse into one number. The
snapshot invariants keep a success from being recorded without the evidence that
makes it comparable.
"""

from __future__ import annotations

import unittest

from llm4mtl.domain import ModelSnapshot, OutcomeStatus, TransformationOutcome


def snapshot(slot: str) -> ModelSnapshot:
    return ModelSnapshot(slot=slot, path=f"out/{slot}.xmi", content_hash="a" * 64)


class OutcomeTests(unittest.TestCase):

    def test_success_carries_a_snapshot_per_slot(self) -> None:
        outcome = TransformationOutcome(
            status=OutcomeStatus.SUCCESS,
            snapshots=(snapshot("families"), snapshot("persons")),
        )

        self.assertTrue(outcome.is_success)
        self.assertEqual(("families", "persons"), outcome.slots)
        self.assertEqual("out/persons.xmi", outcome.snapshot_for("persons").path)

    def test_a_success_without_evidence_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            TransformationOutcome(status=OutcomeStatus.SUCCESS)

    def test_a_failure_cannot_claim_snapshots(self) -> None:
        with self.assertRaises(ValueError):
            TransformationOutcome(
                status=OutcomeStatus.RUNTIME_FAILED, snapshots=(snapshot("target"),)
            )

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
            OutcomeStatus.EMPTY_OUTPUT,
        ):
            with self.subTest(status=status):
                self.assertTrue(status.is_attributable_to_the_transformation)

    def test_empty_output_is_its_own_outcome(self) -> None:
        # A transformation that ran and produced nothing is a semantic result,
        # not a runtime failure.
        outcome = TransformationOutcome(status=OutcomeStatus.EMPTY_OUTPUT)
        self.assertFalse(outcome.is_success)
        self.assertEqual((), outcome.slots)


if __name__ == "__main__":
    unittest.main()
