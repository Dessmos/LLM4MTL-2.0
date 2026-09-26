"""Boundary cases of the stage adapters.

Each stage returns a result before doing any work when it selected nothing or
when it only plans a dry run. These tests pin those early results, and the
branches of the work itself that no other test reaches.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from llm4mtl.domain import GeneratedSuite, ParseObservation, SuiteExecutionObservation
from llm4mtl.semantic_tests.validation import NOT_EXECUTABLE, VALIDATED, SuiteVerdict
from llm4mtl.stages.models import ConfigError, PipelineConfig
from llm4mtl.stages.test_generation import TestGenerationAdapter as GenerationAdapter
from llm4mtl.stages.transformation_parser import TransformationParserAdapter
from llm4mtl.stages.transformation_validation import (
    TransformationValidationAdapter,
    _PairExecutor,
)

SUITE_PARTS = ("Tree2Graph", "candidates", "gpt-5", "few_shot", "suite_001")


def etl_config(**overrides: object) -> PipelineConfig:
    fields: dict[str, object] = {
        "language": "etl",
        "tasks": ["Tree2Graph"],
        "test_models": ["gpt-5"],
        "test_strategies": ["few_shot"],
    }
    fields.update(overrides)
    return PipelineConfig(**fields)  # type: ignore[arg-type]


def passing_observation() -> SuiteExecutionObservation:
    return SuiteExecutionObservation(
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


class TemporaryTreeTestCase(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()

    def make_suite(self, *parts: str) -> Path:
        path = self.root.joinpath("generated", *(parts or SUITE_PARTS))
        path.mkdir(parents=True)
        return path

    def make_file(self, relative: str, text: str = "content") -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class ExtractionBoundaryTests(TemporaryTreeTestCase):

    def test_zero_selected_responses_is_an_error_and_extracts_nothing(self) -> None:
        config = etl_config(responses=[str(self.root / "missing.md")])
        adapter = GenerationAdapter()

        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                with patch("llm4mtl.stages.test_generation.extract_one") as extract:
                    result = adapter.extract(config, dry_run)

                self.assertEqual("extraction", result.name)
                self.assertEqual("error", result.status)
                self.assertEqual({"selected": 0, "failed": 1}, result.counts)
                self.assertEqual({"responses": []}, result.details)
                extract.assert_not_called()

    def test_a_dry_run_plans_the_selected_responses_only(self) -> None:
        response = self.make_file("responses/Tree2Graph.md")
        adapter = GenerationAdapter()

        with patch("llm4mtl.stages.test_generation.extract_one") as extract:
            result = adapter.extract(etl_config(responses=[str(response)]), True)

        self.assertEqual("dry_run", result.status)
        self.assertEqual({"selected": 1}, result.counts)
        extract.assert_not_called()

    def test_a_suite_id_needs_exactly_one_response(self) -> None:
        first = self.make_file("responses/a/Tree2Graph.md")
        second = self.make_file("responses/b/Tree2Graph.md")
        config = etl_config(responses=[str(first), str(second)], suite_id="s1")

        with self.assertRaisesRegex(ConfigError, "exactly one response"):
            GenerationAdapter().extract(config, False)

    def test_extraction_needs_exactly_one_test_model(self) -> None:
        response = self.make_file("responses/Tree2Graph.md")
        config = etl_config(
            responses=[str(response)], test_models=["gpt-5", "claude-sonnet-4"]
        )

        with self.assertRaisesRegex(ConfigError, "exactly one test-generation model"):
            GenerationAdapter().extract(config, False)

    def test_each_response_is_extracted_under_the_run_identity(self) -> None:
        response = self.make_file("responses/Tree2Graph.md")
        adapter = GenerationAdapter()

        with (
            patch(
                "llm4mtl.stages.test_generation.response_target_from_path",
                return_value="target",
            ) as resolve_target,
            patch(
                "llm4mtl.stages.test_generation.extract_one",
                return_value=(False, "no semantic_cases.json block"),
            ),
        ):
            result = adapter.extract(etl_config(responses=[str(response)]), False)

        self.assertEqual("completed", result.status)
        self.assertEqual({"selected": 1, "created": 0, "failed": 1}, result.counts)
        self.assertEqual(
            [
                {
                    "response": str(response),
                    "extracted": False,
                    "detail": "no semantic_cases.json block",
                }
            ],
            result.details["outcomes"],
        )
        overrides = resolve_target.call_args.kwargs
        self.assertEqual("gpt-5", overrides["llm_override"])
        self.assertEqual("few_shot", overrides["strategy_override"])
        self.assertEqual("Tree2Graph", overrides["task_override"])


class SuiteValidationBoundaryTests(TemporaryTreeTestCase):

    def test_zero_selected_suites_is_an_error_for_both_gates(self) -> None:
        adapter = GenerationAdapter()
        config = etl_config(suites=[str(self.root / "missing")])

        for gate in (adapter.technical_validation, adapter.reference_validation):
            with self.subTest(gate=gate.__name__):
                result = gate(config, False)

                self.assertEqual("error", result.status)
                self.assertEqual({"selected": 0, "failed": 1}, result.counts)

    def test_a_dry_run_counts_the_suites_without_validating(self) -> None:
        suite = self.make_suite()
        adapter = GenerationAdapter()

        with patch("llm4mtl.stages.test_generation.check_suite") as check:
            result = adapter.technical_validation(
                etl_config(suites=[str(suite)]), True
            )

        self.assertEqual("dry_run", result.status)
        self.assertEqual({"selected": 1}, result.counts)
        check.assert_not_called()

    def test_skipped_suites_record_the_reason_of_their_gate(self) -> None:
        suite_path = self.make_suite()
        suite = GeneratedSuite(
            "etl", suite_path, "Tree2Graph", "gpt-5", "few_shot", "suite_001"
        )
        adapter = GenerationAdapter()
        config = etl_config(suites=[str(suite_path)])
        cases = (
            ("reference", [SuiteVerdict(suite, NOT_EXECUTABLE)], "SKIPPED_NOT_EXECUTABLE"),
            ("reference", [SuiteVerdict(suite, VALIDATED)], None),
            # A technical verdict is never skipped; only a missing one is.
            ("technical", [], "SKIPPED_ARTIFACT_INVALID"),
        )

        for gate_name, verdicts, expected_reason in cases:
            with self.subTest(gate=gate_name, reason=expected_reason):
                gate = getattr(adapter, f"{gate_name}_validation")
                with (
                    patch.object(adapter, "validation_context", return_value=None),
                    patch.object(adapter, "_suite_verdicts", return_value=verdicts),
                ):
                    result = gate(config, False)

                self.assertEqual(expected_reason, result.details.get("skip_reason"))

    def test_without_a_suite_id_every_matching_suite_in_the_shared_tree_is_selected(
        self,
    ) -> None:
        """Documents current behaviour; whether it should stay is an open question.

        With no suite id and no explicit suites, selection reads the shared
        generated-tests tree, not a run-scoped one. Every suite there that
        matches the task, model and strategy is selected, including suites an
        earlier run left behind.
        """
        own = self.make_suite(*SUITE_PARTS)
        earlier = self.make_suite(*SUITE_PARTS[:-1], "earlier-run_000")
        self.make_suite(*SUITE_PARTS[:2], "claude-sonnet-4", *SUITE_PARTS[3:])
        adapter = GenerationAdapter()

        with patch.object(
            adapter, "generated_tests_root", return_value=self.root / "generated"
        ):
            selected = adapter.select_candidate_suites(etl_config(suite_id=None))

        self.assertEqual(sorted([own, earlier]), selected)


class ExecutionBoundaryTests(TemporaryTreeTestCase):

    def test_no_matching_pair_is_an_error_and_executes_nothing(self) -> None:
        suite = self.make_suite()
        other_task = self.make_file("transformations/OtherTask.etl")
        adapter = TransformationValidationAdapter()
        config = etl_config(transformations=[str(other_task)])

        with (
            patch.object(adapter, "select_validated_suites", return_value=[suite]),
            patch.object(adapter, "_execute_pairs") as execute,
        ):
            result = adapter.semantic_validation(config, False)

        self.assertEqual("error", result.status)
        self.assertEqual(
            {
                "selected_suites": 1,
                "selected_transformations": 1,
                "execution_pairs": 0,
                "failed": 1,
            },
            result.counts,
        )
        self.assertEqual([str(suite)], result.details["reference_validated_suites"])
        execute.assert_not_called()

    def test_execution_needs_a_run_local_engine_workspace(self) -> None:
        adapter = TransformationValidationAdapter()

        with self.assertRaisesRegex(ConfigError, "run-local engine workspace"):
            adapter._execute_pairs(etl_config(), [(Path("suite"), Path("t.etl"))])


class PairExecutionTests(TemporaryTreeTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.suite_path = self.make_suite()
        self.transformation = self.make_file("transformations/Tree2Graph.etl")
        self.adapter = Mock()
        self.adapter.normalize_transformation_failure.return_value = None
        self.executor = _PairExecutor(
            adapter=self.adapter,
            language="etl",
            engine_dir=self.root / "engine",
            observations_root=self.root / "observations",
        )

    def test_a_recorded_observation_is_reused_without_executing(self) -> None:
        observation = passing_observation()

        with (
            patch(
                "llm4mtl.stages.transformation_validation.read_observation",
                return_value=observation,
            ),
            patch(
                "llm4mtl.stages.transformation_validation.record_observation"
            ) as record,
        ):
            pair = self.executor.observe(self.suite_path, self.transformation)

        self.assertIs(observation, pair.observation)
        self.adapter.execute_suite.assert_not_called()
        record.assert_not_called()
        self.assertIn("generated_transformations", pair.evidence_path.parts)
        self.assertEqual("suite_001", pair.evidence_path.parent.name)

    def test_an_unobserved_pair_is_executed_once_and_recorded(self) -> None:
        observation = passing_observation()
        self.adapter.execute_suite.return_value = (observation, "raw evidence")
        recorded = self.root / "recorded.json"

        with (
            patch(
                "llm4mtl.stages.transformation_validation.read_observation",
                return_value=None,
            ),
            patch(
                "llm4mtl.stages.transformation_validation.record_observation",
                return_value=recorded,
            ) as record,
        ):
            pair = self.executor.observe(self.suite_path, self.transformation)

        self.assertEqual(recorded, pair.evidence_path)
        self.adapter.execute_suite.assert_called_once()
        timeout = self.adapter.execute_suite.call_args.args[3]
        self.assertEqual(240, timeout)
        self.assertEqual("raw evidence", record.call_args.kwargs["evidence"])


class SyntaxValidationBoundaryTests(TemporaryTreeTestCase):

    def test_zero_selected_transformations_is_an_error(self) -> None:
        config = etl_config(transformation_selection_locked=True)
        adapter = TransformationParserAdapter()

        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                result = adapter.parse(config, dry_run)

                self.assertEqual("transformation_parsing", result.name)
                self.assertEqual("error", result.status)
                self.assertEqual({"selected": 0, "failed": 1}, result.counts)

    def test_a_dry_run_counts_the_transformations_without_parsing(self) -> None:
        transformation = self.make_file("transformations/Tree2Graph.etl")
        adapter = TransformationParserAdapter()

        with patch("llm4mtl.stages.transformation_parser.language_adapter") as lookup:
            result = adapter.parse(etl_config(transformations=[str(transformation)]), True)

        self.assertEqual("dry_run", result.status)
        self.assertEqual({"selected": 1}, result.counts)
        lookup.assert_not_called()

    def test_parsing_needs_a_run_directory_for_its_evidence(self) -> None:
        transformation = self.make_file("transformations/Tree2Graph.etl")
        adapter = TransformationParserAdapter()

        with self.assertRaisesRegex(ConfigError, "resolved run directory"):
            adapter.parse(etl_config(transformations=[str(transformation)]), False)

    def test_without_an_engine_workspace_parsing_uses_the_runs_own(self) -> None:
        transformation = self.make_file("transformations/Tree2Graph.etl")
        run_dir = self.root / "run"
        language = Mock()
        language.parse_transformations.return_value = {
            transformation: ParseObservation(parsed=False, diagnostic="line 1")
        }
        config = etl_config(
            transformations=[str(transformation)], run_dir=str(run_dir)
        )

        with patch(
            "llm4mtl.stages.transformation_parser.language_adapter",
            return_value=language,
        ):
            result = TransformationParserAdapter().parse(config, False)

        workspace = language.parse_transformations.call_args.args[1]
        self.assertEqual(run_dir / "workspaces" / "etl", workspace.engine_dir)
        self.assertEqual(
            run_dir / "observations" / "syntax-validation", workspace.observations_dir
        )
        self.assertEqual({"selected": 1, "passed": 0, "failed": 1}, result.counts)
        self.assertEqual({str(transformation): None}, result.details["problem_counts"])
        self.assertEqual({str(transformation): "line 1"}, result.details["diagnostics"])


if __name__ == "__main__":
    unittest.main()
