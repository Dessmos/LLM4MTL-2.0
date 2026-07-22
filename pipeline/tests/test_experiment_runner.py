from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm4mtl.experiment_runner.cli import build_parser, config_from_args
from llm4mtl.experiment_runner.config import ConfigError, load_pipeline_config, parse_simple_yaml
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.experiment_runner.orchestrator import ExperimentOrchestrator
from llm4mtl.experiment_runner.adapters.transformation_validation import TransformationValidationAdapter
from llm4mtl.paths import LEGACY_PROJECT_ROOT, TARGET


REPO_ROOT = LEGACY_PROJECT_ROOT


class ConfigTests(unittest.TestCase):
    def test_loads_repository_experiment_yaml(self) -> None:
        config = load_pipeline_config(TARGET.experiments_presets / "etl" / "gpt_tests_vs_claude.yaml")
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


class CliTests(unittest.TestCase):
    def test_suite_id_builds_identity_selection(self) -> None:
        args = build_parser().parse_args(
            [
                "transformations",
                "validate",
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
            ["tests", "extract", "--task", "Tree2Graph", "--suite-id", "suite_001"]
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


class OrchestratorTests(unittest.TestCase):
    def test_dry_run_does_not_create_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            orchestrator = ExperimentOrchestrator(REPO_ROOT)
            orchestrator.runs_root = repo_root / "runs"
            config = PipelineConfig(
                tasks=["Tree2Graph"],
                test_models=["gpt-5"],
                test_strategies=["few_shot"],
                transformation_models=["claude-sonnet-4"],
                dry_run=True,
                run_id="dry-test",
            )
            result = orchestrator.run(config)
            self.assertEqual("dry_run", result.status)
            self.assertFalse((orchestrator.runs_root / "dry-test").exists())
            self.assertEqual(5, len(result.stages))

    def test_semantic_stage_skips_when_parser_passed_nothing(self) -> None:
        config = PipelineConfig(
            tasks=["Tree2Graph"],
            transformation_selection_locked=True,
            transformations=[],
        )
        result = TransformationValidationAdapter(REPO_ROOT).semantic_validation(config, dry_run=True)
        self.assertEqual("skipped", result.status)
        self.assertEqual("SKIPPED_NO_PARSED_TRANSFORMATIONS", result.details["skip_reason"])


if __name__ == "__main__":
    unittest.main()
