"""Stage counts are the funnel's denominators, so each outcome lands in one bucket.

The distinction that carries the science: a suite that could not be executed was
never judged as an oracle. Counting it as an invalid oracle would inflate the
reference-invalid numerator, making the reference-pass rate read as a statement
about oracles when it is partly a statement about broken harnesses.
"""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from llm4mtl.domain import GeneratedSuite, SuiteExecutionObservation
from llm4mtl.experiment_runner.adapters.transformation_validation import (
    TransformationValidationAdapter,
    execution_counts,
)
from llm4mtl.experiment_runner.adapters.test_generation import (
    TestGenerationAdapter as GenerationAdapter,
)
from llm4mtl.experiment_runner.models import PipelineConfig, StageResult
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.semantic_tests.validation import (
    ARTIFACT_INVALID,
    INFRASTRUCTURE_ERROR,
    NOT_EXECUTABLE,
    REFERENCE_INVALID,
    TECHNICALLY_EXECUTABLE,
    VALIDATED,
    SuiteVerdict,
    reference_counts,
    technical_counts,
)
from llm4mtl.stage_contract import outcome_code, stage_status


def verdicts(*statuses: str) -> list[SuiteVerdict]:
    return [
        SuiteVerdict(
            GeneratedSuite(
                "etl",
                Path(f"/suite/{index}"),
                "SmokeTask",
                "gpt-5",
                "few_shot",
                f"s{index}",
            ),
            status,
        )
        for index, status in enumerate(statuses)
    ]


class ReferenceStageCountTests(unittest.TestCase):
    def test_only_judged_suites_reach_the_oracle_verdicts(self) -> None:
        counts = reference_counts(
            verdicts(VALIDATED, REFERENCE_INVALID, NOT_EXECUTABLE, ARTIFACT_INVALID), 4
        )

        self.assertEqual(1, counts["validated"])
        self.assertEqual(1, counts["invalid"])
        self.assertEqual(2, counts["skipped"])
        self.assertEqual(0, counts["infrastructure_errors"])

    def test_a_stage_where_nothing_was_executable_is_skipped_not_passed(self) -> None:
        counts = reference_counts(verdicts(NOT_EXECUTABLE, NOT_EXECUTABLE), 2)
        result = StageResult("reference_validation", "completed", counts)

        self.assertEqual("skipped", stage_status("reference-validation", result))
        self.assertNotEqual("REFERENCE_VALIDATED", outcome_code("reference-validation", result))

    def test_suites_that_produced_no_verdict_are_counted_as_skipped(self) -> None:
        self.assertEqual(2, reference_counts(verdicts(VALIDATED), 3)["skipped"])


class TechnicalStageCountTests(unittest.TestCase):
    def test_executability_and_artifact_validity_are_separate_buckets(self) -> None:
        counts = technical_counts(
            verdicts(TECHNICALLY_EXECUTABLE, NOT_EXECUTABLE, ARTIFACT_INVALID, INFRASTRUCTURE_ERROR),
            4,
        )

        self.assertEqual(1, counts["passed"])
        self.assertEqual(1, counts["failed"])
        self.assertEqual(1, counts["invalid"])
        self.assertEqual(1, counts["infrastructure_errors"])

    def test_artifact_invalid_suites_route_to_test_regeneration(self) -> None:
        counts = technical_counts(verdicts(TECHNICALLY_EXECUTABLE, ARTIFACT_INVALID), 2)
        result = StageResult("technical_validation", "completed", counts)

        self.assertEqual("TEST_SPEC_INVALID", outcome_code("technical-validation", result))


class TestGenerationAdapterValidationTests(unittest.TestCase):
    def test_each_gate_uses_its_validator_and_preserves_verdict_details(self) -> None:
        suite_path = Path("/suite/Tree2Graph/candidates/gpt-5/few_shot/suite_001")
        suite = GeneratedSuite(
            "etl",
            suite_path,
            "Tree2Graph",
            "gpt-5",
            "few_shot",
            "suite_001",
        )
        config = PipelineConfig(language="etl", tasks=["Tree2Graph"])
        adapter = GenerationAdapter(Path("/repository"))
        cases = (
            (False, TECHNICALLY_EXECUTABLE, "technical_validation"),
            (True, VALIDATED, "reference_validation"),
        )

        for judge_as_oracle, status, name in cases:
            verdict = SuiteVerdict(suite, status)
            with self.subTest(name=name):
                with patch.object(
                    adapter,
                    "select_candidate_suites",
                    return_value=[suite_path],
                ):
                    with patch.object(
                        adapter,
                        "validation_context",
                        return_value=object(),
                    ):
                        with patch(
                            "llm4mtl.experiment_runner.adapters.test_generation.suite_from_path",
                            return_value=suite,
                        ):
                            with patch(
                                "llm4mtl.experiment_runner.adapters.test_generation.validate_suite",
                                return_value=verdict,
                            ) as validate:
                                with patch(
                                    "llm4mtl.experiment_runner.adapters.test_generation.check_suite",
                                    return_value=verdict,
                                ) as check:
                                    result = adapter._validate_suites(
                                        name,
                                        config,
                                        dry_run=False,
                                        judge_as_oracle=judge_as_oracle,
                                    )

                selected_validator = validate if judge_as_oracle else check
                other_validator = check if judge_as_oracle else validate
                selected_validator.assert_called_once()
                other_validator.assert_not_called()
                self.assertEqual("completed", result.status)
                self.assertEqual(
                    [{"suite": str(suite_path), "status": status}],
                    result.details["verdicts"],
                )


class ObservationScopeTests(unittest.TestCase):
    def test_observations_are_scoped_to_the_run(self) -> None:
        from llm4mtl.experiment_runner.adapters.test_generation import (
            TestGenerationAdapter as GenerationAdapter,
        )
        from llm4mtl.experiment_runner.models import PipelineConfig
        from llm4mtl.paths import REPO_ROOT

        scoped = GenerationAdapter(REPO_ROOT).observations_root(
            PipelineConfig(
                language="etl",
                run_id="etl-smoke-1",
                run_dir="/tmp/etl-smoke-1",
            )
        )

        self.assertIn("etl-smoke-1", scoped.parts)
        self.assertEqual("observations", scoped.name)

    def test_execution_selection_uses_this_runs_observation_not_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_path = (
                Path(temp_dir)
                / "Tree2Graph"
                / "candidates"
                / "gpt-5"
                / "few_shot"
                / "suite_001"
            )
            suite_path.mkdir(parents=True)
            observation = SuiteExecutionObservation(
                compiled=True,
                tests_discovered=True,
                models_loaded=True,
                engine_started=True,
                assertions_evaluated=True,
                assertions_passed=True,
                timed_out=False,
                maven_exit_code=0,
                failure_stage="",
                error_summary="",
            )
            config = PipelineConfig(
                language="etl",
                tasks=["Tree2Graph"],
                suites=[str(suite_path)],
                run_id="run-001",
            )
            adapter = TransformationValidationAdapter(Path(temp_dir))

            with (
                patch(
                    "llm4mtl.experiment_runner.adapters.transformation_validation.read_observation",
                    return_value=observation,
                ),
                patch.object(
                    adapter,
                    "_observations_root",
                    return_value=Path(temp_dir) / "observations",
                ),
            ):
                selected = adapter.select_validated_suites(config)

            self.assertEqual([suite_path.resolve()], selected)

            with (
                patch(
                    "llm4mtl.experiment_runner.adapters.transformation_validation.read_observation",
                    return_value=None,
                ),
                patch.object(
                    adapter,
                    "_observations_root",
                    return_value=Path(temp_dir) / "observations",
                ),
            ):
                self.assertEqual([], adapter.select_validated_suites(config))

    def test_dry_run_selects_candidates_without_requiring_run_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_path = (
                Path(temp_dir)
                / "Tree2Graph"
                / "candidates"
                / "gpt-5"
                / "few_shot"
                / "suite_001"
            )
            suite_path.mkdir(parents=True)
            config = PipelineConfig(
                language="etl",
                tasks=["Tree2Graph"],
                suites=[str(suite_path)],
            )
            adapter = TransformationValidationAdapter(Path(temp_dir))

            with patch(
                "llm4mtl.experiment_runner.adapters.transformation_validation.read_observation"
            ) as read_observation_mock:
                selected = adapter.select_validated_suites(
                    config,
                    require_observation=False,
                )

            self.assertEqual([suite_path.resolve()], selected)
            read_observation_mock.assert_not_called()


class TransformationExecutionCountTests(unittest.TestCase):
    def unclassified_observation(self, **overrides: object) -> SuiteExecutionObservation:
        fields = dict(
            compiled=True,
            tests_discovered=True,
            models_loaded=False,
            engine_started=False,
            assertions_evaluated=False,
            assertions_passed=False,
            timed_out=False,
            maven_exit_code=1,
            failure_stage="unclassified_runtime",
            error_summary="NullPointerException",
        )
        fields.update(overrides)
        return SuiteExecutionObservation(**fields)  # type: ignore[arg-type]

    def counts_for(self, observation: SuiteExecutionObservation) -> dict[str, int]:
        adapter = EtlAdapter()
        return execution_counts(
            [(observation, adapter.normalize_transformation_failure(observation))]
        )

    def test_unclassified_runtime_on_a_validated_suite_is_a_semantic_failure(self) -> None:
        """Pairs reaching this stage have already passed reference validation.

        The suite compiled, ran, and its assertions held against the trusted
        reference, so an unrecognized throw here is a failure of this pairing.
        Withholding the verdict would drop it out of the denominator; Source
        Diagnosis, not the counter, decides what to refine.
        """
        counts = self.counts_for(self.unclassified_observation())

        self.assertEqual(1, counts["failed"])
        self.assertEqual(1, counts["evaluated"])
        self.assertEqual(0, counts["skipped"])

    def test_evaluated_is_exactly_passed_plus_failed(self) -> None:
        for stage in ("assertion_failure", "engine_runtime", "unclassified_runtime"):
            with self.subTest(stage=stage):
                counts = self.counts_for(
                    self.unclassified_observation(
                        failure_stage=stage,
                        assertions_evaluated=stage == "assertion_failure",
                    )
                )
                self.assertEqual(
                    counts["evaluated"], counts["passed"] + counts["failed"]
                )

    def test_a_pair_the_harness_could_not_run_stays_out_of_the_denominator(self) -> None:
        counts = self.counts_for(
            self.unclassified_observation(failure_stage="model_loading")
        )

        self.assertEqual(1, counts["skipped"])
        self.assertEqual(0, counts["evaluated"])


if __name__ == "__main__":
    unittest.main()
