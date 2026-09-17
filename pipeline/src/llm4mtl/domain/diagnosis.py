"""Source Diagnosis verdicts, and the one rule that combines several of them.

A diagnosis classifies one recorded failure as a defect of the transformation,
a defect of the test, or as ambiguous. A run can hold several verdicts: one
execution attempt fails several pairs, and each prepared report is diagnosed on
its own. Wherever those verdicts are combined into one decision, this is the rule.
It is stated here, in the language-neutral core, because three layers apply it:
the orchestration routes on it, the run's terminal result records it, and the
evaluation counts it. Three restatements would be three chances to disagree.
"""

from __future__ import annotations

from typing import Iterable

TRANSFORMATION_DEFECT = "TRANSFORMATION_DEFECT"
TEST_DEFECT = "TEST_DEFECT"
AMBIGUOUS = "AMBIGUOUS"

DIAGNOSIS_CLASSIFICATIONS = frozenset({TRANSFORMATION_DEFECT, TEST_DEFECT, AMBIGUOUS})


def aggregate_classifications(classifications: Iterable[str | None]) -> str | None:
    """The single verdict over every recorded classification, or ``None`` for none.

    Conservative on purpose, and never a majority vote: one ambiguous verdict, or
    one of each defect kind, means the evidence points at both artefacts, and
    repairing either one on that basis is the mistake Source Diagnosis exists to
    prevent. Missing verdicts (``None``) carry no evidence and are skipped.
    """
    present = [classification for classification in classifications if classification]
    if not present:
        return None
    if AMBIGUOUS in present:
        return AMBIGUOUS
    has_transformation_defect = TRANSFORMATION_DEFECT in present
    has_test_defect = TEST_DEFECT in present
    if has_transformation_defect and has_test_defect:
        return AMBIGUOUS
    return TRANSFORMATION_DEFECT if has_transformation_defect else TEST_DEFECT
