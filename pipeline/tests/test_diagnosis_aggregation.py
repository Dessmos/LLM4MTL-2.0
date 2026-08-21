"""Counting failures, not reports about failures.

One broken model reference in a transformation fails every test case that uses
it, so preparation writes one report per case and the subworkflow diagnoses each
of them. Those are separate observations and the pipeline is right to keep them
all. What must not follow is "Source Diagnosis found three transformation
defects": there was one defect, three affected cases, and three verdicts about
it. These tests pin the clustering that keeps the two apart, and the agreement
figure that makes the consistency of those verdicts measurable.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from llm4mtl.evaluation.diagnosis_aggregation import (
    DiagnosisAggregationError,
    aggregate_run_diagnoses,
    failure_fingerprint,
)
from llm4mtl.serialization.json_io import write_json

RUN_ID = "agg-1"
TRANSFORMATION_SHA = "a" * 64
TRACE = (
    "Type 'Source!Tree' not found\n"
    "\tat org.eclipse.epsilon.eol.dom.TypeExpression.execute(TypeExpression.java:97)\n"
)


def _report(
    *,
    method: str,
    summary: str = "Type 'Source!Tree' not found",
    stage: str = "unclassified_runtime",
    trace: str = TRACE,
    exception: str = "EolRuntimeException",
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "report_type": "semantic_test_case_failure",
        "test_case_result": {
            "semantic_status": "execution_error",
            "failure": {"kind": "runtime_error", "message": summary},
            "execution": {
                "observation": {
                    "failure_stage": stage,
                    # Surefire names the method that reached the fault first, so
                    # the same fault produces a different summary per report.
                    "error_summary": f"{method}: {summary}",
                },
                "error": {
                    "exceptions": [{"type": exception, "message": summary}],
                    "stack_traces": [trace],
                },
            },
            "versions": {"generated_transformation": {"sha256": TRANSFORMATION_SHA}},
        },
    }


class FailureFingerprintTests(unittest.TestCase):
    def test_the_same_fault_in_different_cases_has_one_fingerprint(self) -> None:
        first = failure_fingerprint(_report(method="singleRootTree"))
        second = failure_fingerprint(_report(method="threeLevelTree"))

        self.assertEqual(
            first["failure_fingerprint"], second["failure_fingerprint"]
        )
        # The method prefix is what differed, and normalization drops it.
        self.assertEqual(
            "Type 'Source!Tree' not found", first["normalized_error_summary"]
        )
        self.assertEqual(
            "org.eclipse.epsilon.eol.dom.TypeExpression.execute(TypeExpression.java:#)",
            first["top_stack_frame"],
        )

    def test_the_same_message_from_a_different_place_is_a_different_failure(
        self,
    ) -> None:
        """Deduplicating on the message alone would merge unrelated faults."""
        here = failure_fingerprint(_report(method="a"))
        elsewhere = failure_fingerprint(
            _report(
                method="a",
                trace="Type 'Source!Tree' not found\n\tat other.Place.run(Place.java:12)\n",
            )
        )
        other_transformation = failure_fingerprint(_report(method="a"))
        other_transformation_report = _report(method="a")
        other_transformation_report["test_case_result"]["versions"][
            "generated_transformation"
        ]["sha256"] = "b" * 64

        self.assertNotEqual(
            here["failure_fingerprint"], elsewhere["failure_fingerprint"]
        )
        self.assertNotEqual(
            other_transformation["failure_fingerprint"],
            failure_fingerprint(other_transformation_report)["failure_fingerprint"],
        )


class RunAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run_dir = self.root / "runs" / RUN_ID
        self.diagnoses = self.root / "diagnoses"
        self.reports_dir = (
            self.run_dir / "diagnosis" / "execution" / "attempt-001" / "reports"
        )

    def _write_index(self, reports: list[dict[str, Any]]) -> None:
        write_json(
            self.run_dir / "diagnosis" / "execution" / "attempt-001" / "index.json",
            {
                "schema_version": "1.0",
                "run_id": RUN_ID,
                "attempt": 1,
                "pairs": [
                    {
                        "suite": "/app/artifacts/.../suite_001",
                        "transformation": "/app/artifacts/.../Tree2Graph.etl",
                        "reports": reports,
                        "skipped": [],
                    }
                ],
            },
        )

    def _write_case(self, case: str, method: str, **facets: Any) -> dict[str, Any]:
        path = self.reports_dir / f"{case}.json"
        write_json(path, _report(method=method, **facets))
        return {
            "status": "created",
            "scope": "test_case",
            "test_case_id": case,
            "assertion_id": None,
            "eligible": True,
            "report": f"artifacts/work/runs/{RUN_ID}/diagnosis/execution/"
            f"attempt-001/reports/{case}.json",
        }

    def _write_verdict(self, attempt: int, case: str, classification: str) -> None:
        write_json(
            self.diagnoses / RUN_ID / f"attempt-{attempt:03d}" / "diagnosis.json",
            {
                "schema_version": "1.0",
                "classification": classification,
                "evidence_ref": (
                    f"diagnosis/execution/attempt-001/reports/{case}.json"
                ),
                "rationale": "recorded by a test",
                "provider": "openai",
                "model": "gpt-5",
                "created_at": "2026-08-20T13:56:00+00:00",
            },
        )

    def test_one_defect_across_three_cases_counts_as_one_failure(self) -> None:
        cases = ["single_root", "parent_child", "three_level"]
        self._write_index(
            [self._write_case(case, method=f"{case}Test") for case in cases]
        )
        for attempt, case in enumerate(cases, start=1):
            self._write_verdict(attempt, case, "TRANSFORMATION_DEFECT")

        aggregated = aggregate_run_diagnoses(self.run_dir, 1, self.diagnoses)

        pair = aggregated["pairs"][0]
        self.assertEqual(3, pair["diagnosis_reports"])
        self.assertEqual(3, pair["affected_test_cases"])
        self.assertEqual(1, pair["unique_failure_clusters"])
        self.assertEqual("TRANSFORMATION_DEFECT", pair["aggregate_verdict"])
        cluster = pair["clusters"][0]
        self.assertEqual(sorted(cases), sorted(cluster["test_cases"]))
        self.assertEqual(3, cluster["diagnosed"])
        # Three independent verdicts, all the same: that is what makes the
        # figure a measurement of consistency rather than an assumption.
        self.assertEqual(1.0, cluster["agreement"])
        self.assertEqual(1.0, aggregated["totals"]["agreement"])
        self.assertEqual("TRANSFORMATION_DEFECT", aggregated["aggregate_verdict"])

    def test_two_distinct_failures_stay_two(self) -> None:
        first = self._write_case("single_root", method="singleRootTest")
        second = self._write_case(
            "parent_child",
            method="parentChildTest",
            summary="Cannot cast Node to Edge",
            exception="ClassCastException",
            trace="Cannot cast\n\tat generated.Rule.apply(Rule.java:12)\n",
        )
        self._write_index([first, second])
        self._write_verdict(1, "single_root", "TRANSFORMATION_DEFECT")
        self._write_verdict(2, "parent_child", "TEST_DEFECT")

        aggregated = aggregate_run_diagnoses(self.run_dir, 1, self.diagnoses)

        pair = aggregated["pairs"][0]
        self.assertEqual(2, pair["unique_failure_clusters"])
        self.assertEqual([1, 1], [cluster["reports"] for cluster in pair["clusters"]])
        # Each failure keeps its own verdict; the pair-level aggregate is the
        # conservative combination the pipeline routes on.
        self.assertEqual(
            {"TRANSFORMATION_DEFECT", "TEST_DEFECT"},
            {cluster["verdict"] for cluster in pair["clusters"]},
        )
        self.assertEqual("AMBIGUOUS", pair["aggregate_verdict"])

    def test_disagreeing_verdicts_about_one_failure_are_visible(self) -> None:
        cases = ["single_root", "parent_child", "three_level"]
        self._write_index(
            [self._write_case(case, method=f"{case}Test") for case in cases]
        )
        self._write_verdict(1, "single_root", "TRANSFORMATION_DEFECT")
        self._write_verdict(2, "parent_child", "TRANSFORMATION_DEFECT")
        self._write_verdict(3, "three_level", "TEST_DEFECT")

        cluster = aggregate_run_diagnoses(self.run_dir, 1, self.diagnoses)["pairs"][0][
            "clusters"
        ][0]

        self.assertEqual(3, cluster["reports"])
        self.assertEqual(3, cluster["diagnosed"])
        self.assertAlmostEqual(0.6667, cluster["agreement"], places=4)
        # Two of one kind and one of the other still means both artefacts.
        self.assertEqual("AMBIGUOUS", cluster["verdict"])

    def test_a_report_nobody_diagnosed_is_counted_but_not_invented(self) -> None:
        self._write_index([self._write_case("single_root", method="singleRootTest")])

        aggregated = aggregate_run_diagnoses(self.run_dir, 1, self.diagnoses)

        cluster = aggregated["pairs"][0]["clusters"][0]
        self.assertEqual(1, cluster["reports"])
        self.assertEqual(0, cluster["diagnosed"])
        self.assertIsNone(cluster["verdict"])
        self.assertIsNone(cluster["agreement"])
        self.assertIsNone(aggregated["totals"]["agreement"])

    def test_an_attempt_without_prepared_evidence_is_refused(self) -> None:
        with self.assertRaises(DiagnosisAggregationError):
            aggregate_run_diagnoses(self.run_dir, 1, self.diagnoses)


if __name__ == "__main__":
    unittest.main()
