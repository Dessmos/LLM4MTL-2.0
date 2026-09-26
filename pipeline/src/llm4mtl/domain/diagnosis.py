"""Source Diagnosis verdicts, and the one rule that combines several of them.

A diagnosis classifies one recorded failure as a defect of the transformation,
a defect of the test, or as ambiguous. A run can hold several verdicts, because
each prepared failure report is diagnosed on its own. Wherever Python combines
them into one decision, it uses this rule: the run's terminal result
(``run_store.results``) and the diagnosis clustering
(``semantic_tests.diagnosis_aggregation``) both call it.

The n8n master workflow routes on the same rule, written again in its own
JavaScript. A change here must be made there too.
"""

from __future__ import annotations

from typing import Iterable

TRANSFORMATION_DEFECT = "TRANSFORMATION_DEFECT"
TEST_DEFECT = "TEST_DEFECT"
AMBIGUOUS = "AMBIGUOUS"


def aggregate_classifications(classifications: Iterable[str | None]) -> str | None:
    """The single verdict over every recorded classification, or ``None`` for none.

    Conservative on purpose, never a majority vote: one ambiguous verdict, or one
    of each defect kind, means the evidence points at both artefacts. Repairing
    either one on that evidence is the mistake Source Diagnosis exists to
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
