from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from llm4mtl.experiment_runner.cli import (
    build_parser,
    config_from_args,
    emit_result,
    main,
    validate_command_constraints,
)
from llm4mtl.experiment_runner.config import (
    ConfigError,
    load_pipeline_config,
    parse_simple_yaml,
    validate_config,
)
from llm4mtl.experiment_runner.models import RunResult
from llm4mtl.stages.models import PipelineConfig, StageResult
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.stages.transformation_validation import TransformationValidationAdapter
from llm4mtl.paths import REPO_ROOT, TARGET, ArtifactRoots
from llm4mtl.semantic_tests.failure_report import DIFF_FIELDS, FailureReportError
from llm4mtl.semantic_tests.failure_report.request import (
    ReportRequest,
    _validate_difference,
)



class ConfigTests(unittest.TestCase):

    def test_loads_repository_experiment_yaml(self) -> None:
        config = load_pipeline_config(
            TARGET.experiments / "presets" / "etl" / "gpt_tests_vs_claude.yaml"
        )
        self.assertEqual(["Tree2Graph"], config.tasks)
        self.assertEqual(["gpt-5"], config.test_models)
        self.assertEqual(["claude-sonnet-4"], config.transformation_models)
        self.assertIn("grammar", config.transformation_strategies)

    def test_fallback_yaml_parser_supports_nested_lists(self) -> None:
        payload = parse_simple_yaml(
            "language: etl\n"
            "tasks:\n"
            "  - Tree2Graph\n"
            "execution:\n"
            "  resume: true\n"
        )
        self.assertEqual(["Tree2Graph"], payload["tasks"])
        self.assertTrue(payload["execution"]["resume"])

    def test_fallback_yaml_parser_rejects_unexpected_indentation(self) -> None:
        with self.assertRaisesRegex(ConfigError, "Unexpected indentation near: task"):
            parse_simple_yaml("language: etl\n  task: Tree2Graph\n")

    def test_fallback_yaml_parser_supports_mapping_list_items(self) -> None:
        payload = parse_simple_yaml(
            "items:\n"
            "  - name: first\n"
            "    enabled: true\n"
            "  - values:\n"
            "      - one\n"
        )

        self.assertEqual(
            [
                {"name": "first", "enabled": True},
                {"values": ["one"]},
            ],
            payload["items"],
        )

    def test_fallback_yaml_parser_preserves_empty_list_items(self) -> None:
        payload = parse_simple_yaml("items:\n  -\nnext: value\n")

        self.assertEqual([None], payload["items"])
        self.assertEqual("value", payload["next"])

    def test_a_config_cannot_silently_default_to_etl(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "missing-language.yaml"
            config_path.write_text("tasks: [Tree2Graph]\n", encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_pipeline_config(config_path)

    def test_config_validation_preserves_selection_before_stage_errors(self) -> None:
        config = PipelineConfig(
            language="etl",
            tasks=["Tree2Graph"],
            test_models=["unknown-model"],
            start_stage="unknown-stage",
        )

        with self.assertRaisesRegex(ConfigError, "Unsupported model"):
            validate_config(config)

    def test_extract_command_constraint_error_order_is_preserved(self) -> None:
        config = PipelineConfig(
            language="etl",
            command="tests.extract",
            suite_id="suite_001",
            responses=[],
            all_tasks=True,
        )

        with self.assertRaisesRegex(
            ConfigError,
            "--suite-id requires exactly one --response",
        ):
            validate_command_constraints(config)

    def test_explicit_suite_bypasses_suite_identity_requirements(self) -> None:
        config = PipelineConfig(
            language="etl",
            command="tests.validate",
            suite_id="suite_001",
            suites=["suite/path"],
        )

        validate_command_constraints(config)


class DifferenceValidationTests(unittest.TestCase):

    def test_shape_errors_preserve_missing_then_unknown_order(self) -> None:
        with self.assertRaisesRegex(
            FailureReportError,
            "missing fields:.*; unknown fields: unexpected",
        ):
            _validate_difference({"missing_elements": [], "unexpected": []})

    def test_each_difference_field_must_remain_an_array(self) -> None:
        difference = {field: [] for field in DIFF_FIELDS}
        difference["wrong_types"] = "not-an-array"

        with self.assertRaisesRegex(
            FailureReportError,
            "actual_vs_expected.wrong_types must be an array",
        ):
            _validate_difference(difference)


class CliTests(unittest.TestCase):

    def test_text_result_output_preserves_stage_detail_order(self) -> None:
        result = RunResult(
            run_id="dry-test",
            status="dry_run",
            command="pipeline.run",
            run_dir="artifacts/work/runs/batch_001/dry-test",
            stages=[
                StageResult(
                    name="transformation_validation",
                    status="dry_run",
                    counts={
                        "selected_suites": 2,
                        "selected_transformations": 1,
                        "execution_pairs": 2,
                    },
                    details={
                        "pairs": ["pair-one", "pair-two"],
                        "results_file": "artifacts/work/results.json",
                        "artifacts": [{"status": "candidate", "path": "suite-001"}],
                    },
                )
            ],
        )
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            emit_result(result, "text")

        self.assertEqual(
            "Run: dry-test\n"
            "Status: dry_run\n"
            "transformation_validation: dry_run selected_suites=2 "
            "selected_transformations=1 execution_pairs=2\n"
            "Candidate suites awaiting reference validation: 2\n"
            "Selected transformations: 1\n"
            "Potential execution pairs: 2\n"
            "pair-one\n"
            "pair-two\n"
            "Results: artifacts/work/results.json\n"
            "candidate: suite-001\n"
            "Run metadata: artifacts/work/runs/batch_001/dry-test\n",
            stdout.getvalue(),
        )

    def test_a_direct_command_requires_an_explicit_language(self) -> None:
        with self.assertRaises(SystemExit):
            build_parser().parse_args(["tests", "extract", "--task", "Tree2Graph"])

    def test_options_that_did_nothing_are_rejected(self) -> None:
        base = ["tests", "extract", "--language", "etl", "--task", "Tree2Graph"]
        for option in ("--overwrite", "--no-overwrite", "--keep-workspace", "--verbose"):
            with self.subTest(option=option):
                with patch("sys.stderr", new_callable=io.StringIO):
                    with self.assertRaises(SystemExit):
                        build_parser().parse_args([*base, option])

    def test_suite_id_builds_identity_selection(self) -> None:
        args = build_parser().parse_args(
            [
                "transformations",
                "validate",
                "--language",
                "etl",
                "--task",
                "Tree2Graph",
                "--test-model",
                "gpt-5",
                "--test-strategy",
                "few_shot",
                "--suite-id",
                "suite_001",
                "--transformation-model",
                "claude-sonnet-4",
                "--dry-run",
            ]
        )
        config = config_from_args(args)
        self.assertEqual("suite_001", config.suite_id)
        self.assertEqual("transformations.validate", config.command)

    def test_extract_suite_id_requires_explicit_response(self) -> None:
        args = build_parser().parse_args(
            [
                "tests",
                "extract",
                "--language",
                "etl",
                "--task",
                "Tree2Graph",
                "--suite-id",
                "suite_001",
            ]
        )
        with self.assertRaises(ConfigError):
            config_from_args(args)

    def test_config_rejects_selector_override(self) -> None:
        args = build_parser().parse_args(
            [
                "pipeline",
                "run",
                "--config",
                "experiments/etl/gpt_tests_vs_claude.yaml",
                "--task",
                "Tree2Graph",
            ]
        )
        with self.assertRaises(ConfigError):
            config_from_args(args)

    def test_diagnosis_report_dispatches_through_the_orchestrator(self) -> None:
        report = {
            "identity": {"run_id": "run-001"},
            "source_diagnosis": {"eligible": True},
        }
        stdout = io.StringIO()
        with patch.object(
            ExperimentOrchestrator,
            "assemble_failure_report",
            return_value=report,
        ) as assemble:
            with redirect_stdout(stdout):
                exit_code = main(
                    [
                        "diagnosis",
                        "report",
                        "--request",
                        "artifacts/work/request.json",
                        "--output",
                        "artifacts/work/report.json",
                    ]
                )

        self.assertEqual(0, exit_code)
        assemble.assert_called_once_with(
            Path("artifacts/work/request.json"),
            Path("artifacts/work/report.json"),
        )
        self.assertIn("Diagnosis eligible: true", stdout.getvalue())

    def test_failure_report_requires_explicit_runtime_evidence_paths(self) -> None:
        payload = {
            "run_manifest": "README.md",
            "syntax_evidence": "README.md",
            "execution_evidence": "README.md",
            "generated_execution": "README.md",
            "reference_execution": None,
            "test_case_id": "case-1",
            "assertion_id": "assertion-001",
            "attempt": 1,
            "actual_target_models": ["README.md"],
            "surefire_reports": ["README.md"],
            "execution_log": None,
            "actual_vs_expected": None,
        }

        incomplete = {**payload}
        del incomplete["actual_target_models"]
        with self.assertRaisesRegex(
            FailureReportError, "actual_target_models must be an array of paths"
        ):
            ReportRequest.from_payload(incomplete)

        # `surefire_reports` may be omitted only when the run archived the
        # execution evidence itself. Here the generated execution has no archive
        # beside it, so an omitted field is still refused rather than producing a
        # report with silently empty runtime evidence.
        incomplete = {**payload}
        del incomplete["surefire_reports"]
        with self.assertRaisesRegex(FailureReportError, "archived execution evidence"):
            ReportRequest.from_payload(incomplete)


class OrchestratorTests(unittest.TestCase):

    def test_failure_report_command_delegates_to_the_shared_assembler(self) -> None:
        orchestrator = ExperimentOrchestrator()
        payload = {"attempt": 1}
        expected = {"report_type": "semantic_test_case_failure"}
        with patch(
            "llm4mtl.experiment_runner.orchestrator.read_request_payload",
            return_value=payload,
        ) as read_payload:
            with patch(
                "llm4mtl.experiment_runner.orchestrator.write_report",
                return_value=expected,
            ) as write_report:
                actual = orchestrator.assemble_failure_report(
                    Path("request.json"),
                    Path("artifacts/work/report.json"),
                )

        self.assertEqual(expected, actual)
        read_payload.assert_called_once_with(Path("request.json"))
        write_report.assert_called_once_with(
            payload,
            Path("artifacts/work/report.json"),
            scope="test_case",
        )

    def test_dry_run_does_not_create_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            orchestrator = ExperimentOrchestrator()
            orchestrator.artifacts = ArtifactRoots(repo_root)
            config = PipelineConfig(
                language="etl",
                tasks=["Tree2Graph"],
                test_models=["gpt-5"],
                test_strategies=["few_shot"],
                transformation_models=["claude-sonnet-4"],
                dry_run=True,
                run_id="dry-test",
            )
            result = orchestrator.run(config)
            self.assertEqual("dry_run", result.status)
            # Neither the run nor the batch it previewed is claimed by a dry run.
            self.assertFalse(orchestrator.artifacts.runs.exists())
            self.assertEqual(5, len(result.stages))

    def test_semantic_stage_skips_when_parser_passed_nothing(self) -> None:
        config = PipelineConfig(
            language="etl",
            tasks=["Tree2Graph"],
            transformation_selection_locked=True,
            transformations=[],
        )
        result = TransformationValidationAdapter().semantic_validation(
            config, dry_run=True
        )
        self.assertEqual("skipped", result.status)
        self.assertEqual(
            "SKIPPED_NO_PARSED_TRANSFORMATIONS", result.details["skip_reason"]
        )

    def test_semantic_dry_run_preserves_pairing_and_detail_keys(self) -> None:
        config = PipelineConfig(language="etl", tasks=["Tree2Graph"])
        adapter = TransformationValidationAdapter()
        suite = Path("/generated/Tree2Graph/candidates/gpt-5/grammar/suite_001")
        transformation = Path("/generated/Tree2Graph.etl")

        with patch.object(
            adapter,
            "select_validated_suites",
            return_value=[suite],
        ) as select_suites:
            with patch.object(
                adapter,
                "select_transformations",
                return_value=[transformation],
            ):
                result = adapter.semantic_validation(config, dry_run=True)

        self.assertEqual("dry_run", result.status)
        self.assertEqual(1, result.counts["execution_pairs"])
        self.assertEqual(
            [str(suite)],
            result.details["suite_candidates_awaiting_reference_validation"],
        )
        self.assertNotIn("reference_validated_suites", result.details)
        select_suites.assert_called_once_with(config, require_observation=False)


class ConfigBoundaryTests(unittest.TestCase):

    def test_disabled_extraction_starts_the_run_at_technical_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                '{"language": "etl", "tasks": ["Tree2Graph"],'
                ' "test_suites": {"extraction": {"enabled": false}}}',
                encoding="utf-8",
            )
            config = load_pipeline_config(path)

        self.assertEqual("technical", config.start_stage)
        self.assertEqual("semantic", config.stop_after)

    def test_a_config_with_a_blank_language_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text('{"language": " ", "tasks": ["Tree2Graph"]}', encoding="utf-8")

            with self.assertRaisesRegex(ConfigError, "non-empty language"):
                load_pipeline_config(path)

    def test_direct_commands_default_to_the_whole_pipeline_and_text_output(
        self,
    ) -> None:
        args = build_parser().parse_args(
            ["tests", "extract", "--language", "etl", "--task", "Tree2Graph"]
        )
        config = config_from_args(args)

        self.assertEqual("extract", config.start_stage)
        self.assertEqual("semantic", config.stop_after)
        self.assertEqual("text", config.output_format)
        self.assertEqual([], config.responses)

    def test_diagnosis_commands_accept_only_the_known_output_formats(self) -> None:
        commands = (
            ["diagnosis", "report", "--request", "r.json", "--output", "o.json"],
            ["diagnosis", "prepare", "--run", "run-001", "--batch", "batch_001"],
            ["diagnosis", "aggregate", "--run", "run-001", "--batch", "batch_001"],
        )
        for command in commands:
            with self.subTest(command=command[1]):
                parser = build_parser()
                self.assertEqual("text", parser.parse_args(command).output_format)
                self.assertEqual(
                    "json",
                    parser.parse_args([*command, "--output-format", "json"]).output_format,
                )
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args([*command, "--output-format", "yaml"])


class StageSequenceTests(unittest.TestCase):

    def stage_names(self, **overrides: object) -> list[str]:
        config = PipelineConfig(language="etl", tasks=["Tree2Graph"], **overrides)  # type: ignore[arg-type]
        orchestrator = ExperimentOrchestrator()
        return [name for name, _ in orchestrator.stage_sequence(config)]

    def test_standalone_commands_run_their_own_stages(self) -> None:
        cases = (
            ({"command": "tests.extract"}, ["extraction"]),
            ({"command": "transformations.parse"}, ["transformation_parsing"]),
            ({"command": "transformations.validate"}, ["transformation_validation"]),
            (
                {"command": "tests.validate", "test_validation_stage": "technical"},
                ["technical_validation"],
            ),
            (
                {"command": "tests.validate", "test_validation_stage": "reference"},
                ["reference_validation"],
            ),
            (
                {"command": "tests.validate", "test_validation_stage": "all"},
                ["technical_validation", "reference_validation"],
            ),
        )
        for overrides, expected in cases:
            with self.subTest(**overrides):
                self.assertEqual(expected, self.stage_names(**overrides))

    def test_a_pipeline_runs_its_stage_range_without_disabled_stages(self) -> None:
        self.assertEqual(
            ["technical_validation", "transformation_parsing"],
            self.stage_names(
                start_stage="technical",
                stop_after="parsing",
                reference_validation=False,
            ),
        )

    def test_each_stage_runs_the_matching_adapter_method(self) -> None:
        orchestrator = ExperimentOrchestrator()
        config = PipelineConfig(language="etl", tasks=["Tree2Graph"])

        self.assertEqual(
            [
                ("extraction", orchestrator.tests.extract),
                ("technical_validation", orchestrator.tests.technical_validation),
                ("reference_validation", orchestrator.tests.reference_validation),
                ("transformation_parsing", orchestrator.parser.parse),
                (
                    "transformation_validation",
                    orchestrator.transformations.semantic_validation,
                ),
            ],
            orchestrator.stage_sequence(config),
        )


def failed_stage(name: str) -> StageResult:
    return StageResult(name, "completed", {"selected": 1, "failed": 1})


def passed_stage(name: str) -> StageResult:
    return StageResult(name, "completed", {"selected": 1, "failed": 0})


class LocalRunTests(unittest.TestCase):
    """Whole local runs, with the stages replaced and the runs root in a temp tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.artifacts = ArtifactRoots(Path(self._tmp.name).resolve())
        repo_root_patcher = patch(
            "llm4mtl.experiment_runner.orchestrator.REPO_ROOT",
            self.artifacts.artifacts_work,
        )
        repo_root_patcher.start()
        self.addCleanup(repo_root_patcher.stop)
        self.orchestrator = ExperimentOrchestrator()
        self.orchestrator.artifacts = self.artifacts
        self.extract = patch.object(
            self.orchestrator.tests,
            "extract",
            side_effect=lambda *_: failed_stage("extraction"),
        ).start()
        self.parse = patch.object(
            self.orchestrator.parser,
            "parse",
            side_effect=lambda *_: passed_stage("transformation_parsing"),
        ).start()
        self.addCleanup(patch.stopall)

    def config(self, run_id: str, **overrides: object) -> PipelineConfig:
        fields: dict[str, object] = {
            "language": "etl",
            "tasks": ["Tree2Graph"],
            "test_models": ["gpt-5"],
            "test_strategies": ["few_shot"],
            "transformation_models": ["gpt-5"],
            "transformation_strategies": ["grammar"],
            "stop_after": "parsing",
            "technical_validation": False,
            "reference_validation": False,
            "run_id": run_id,
        }
        fields.update(overrides)
        return PipelineConfig(**fields)  # type: ignore[arg-type]

    def test_fail_fast_stops_after_the_first_failing_stage(self) -> None:
        for fail_fast, expected in (
            (True, ["extraction"]),
            (False, ["extraction", "transformation_parsing"]),
        ):
            with self.subTest(fail_fast=fail_fast):
                result = self.orchestrator.run(
                    self.config(f"fail-fast-{fail_fast}".lower(), fail_fast=fail_fast)
                )

                self.assertEqual(expected, [stage.name for stage in result.stages])
                self.assertEqual("completed_with_failures", result.status)

    def test_an_existing_run_is_reused_only_on_resume_or_force(self) -> None:
        first = self.orchestrator.run(self.config("existing-run"))
        batch_id = first.run_dir.split("/")[-2] if first.run_dir else None

        with self.assertRaisesRegex(ConfigError, "Run already exists: existing-run"):
            self.orchestrator.run(self.config("existing-run", batch_id=batch_id))

    def test_resume_reuses_a_completed_stage_with_matching_hashes(self) -> None:
        first = self.orchestrator.run(self.config("resumed-run"))
        batch_id = first.run_dir.split("/")[-2] if first.run_dir else None
        self.parse.reset_mock()

        resumed = self.orchestrator.run(
            self.config("resumed-run", batch_id=batch_id, resume=True)
        )

        parsing = resumed.stages[-1]
        self.assertEqual("resumed", parsing.status)
        self.assertEqual(
            "matching config and input hashes", parsing.details["resume_reason"]
        )
        # Planned again to compare hashes, but not executed again.
        self.assertEqual([True], [call.args[1] for call in self.parse.call_args_list])

    def test_diagnosis_needs_a_recorded_execution_attempt(self) -> None:
        first = self.orchestrator.run(self.config("no-execution"))
        batch_id = first.run_dir.split("/")[-2] if first.run_dir else ""

        for command in (
            self.orchestrator.prepare_diagnosis_evidence,
            self.orchestrator.aggregate_diagnosis_evidence,
        ):
            with self.subTest(command=command.__name__):
                with self.assertRaisesRegex(ConfigError, "recorded no execution attempt"):
                    command(batch_id, "no-execution")


if __name__ == "__main__":
    unittest.main()
