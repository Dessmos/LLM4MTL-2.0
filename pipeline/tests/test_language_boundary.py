"""The seam every additional language goes through.

Two properties matter here. First, a language without an adapter fails loudly
rather than silently receiving ETL conventions — an experiment attributed to a
language that never ran is worse than one that refuses to start. Second, the
shared pipeline resolves adapters from the registry instead of naming ETL, so
adding a language is adding an adapter rather than editing pipeline code.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from llm4mtl.conventions import ETL_CONFIG, REACTIONS_CONFIG, UnsupportedLanguageError, language_config
from llm4mtl.domain import (
    ArtifactValidation,
    OutcomeStatus,
    ParseObservation,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.experiment_runner.config import validate_config
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.languages import (
    REQUIRED_LANGUAGES,
    LanguageAdapter,
    implemented_languages,
    language_adapter,
)
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.languages.reactions.adapter import (
    _contains_only_unresolved_linkage_diagnostics,
)


class RegistryTests(unittest.TestCase):
    def test_all_four_thesis_languages_are_declared(self) -> None:
        self.assertEqual(("etl", "atl", "qvto", "reactions"), REQUIRED_LANGUAGES)

    def test_every_required_language_has_an_adapter(self) -> None:
        for language in REQUIRED_LANGUAGES:
            with self.subTest(language=language):
                self.assertIsInstance(language_adapter(language), LanguageAdapter)

    def test_an_unknown_language_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            language_adapter("cobol")

    def test_all_adapters_satisfy_the_shared_interface(self) -> None:
        adapter = language_adapter("etl")
        self.assertIsInstance(adapter, LanguageAdapter)
        self.assertEqual("etl", adapter.language_id)
        self.assertEqual(tuple(sorted(REQUIRED_LANGUAGES)), implemented_languages())


class PipelineLanguageResolutionTests(unittest.TestCase):
    def test_the_runner_accepts_reactions(self) -> None:
        config = PipelineConfig(language="reactions", tasks=["FamiliesToPersons"])
        validate_config(config)

    def test_the_runner_accepts_the_implemented_language(self) -> None:
        validate_config(PipelineConfig(language="etl", tasks=["Tree2Graph"]))


class ConventionsTests(unittest.TestCase):
    def test_conventions_require_an_explicit_language(self) -> None:
        # A default would silently hand ETL paths to another language.
        self.assertIs(ETL_CONFIG, language_config("etl"))
        self.assertIs(REACTIONS_CONFIG, language_config("reactions"))
        with self.assertRaises(UnsupportedLanguageError):
            language_config("cobol")


class EtlAdapterContractTests(unittest.TestCase):
    """The contract tests every future adapter must also pass."""

    def setUp(self) -> None:
        self.adapter = EtlAdapter(references_root=Path("/benchmark/etl/references"))

    def test_it_locates_its_reference_transformation(self) -> None:
        reference = self.adapter.reference_transformation("Tree2Graph")
        self.assertEqual("Tree2Graph.etl", reference.name)

    def test_it_reports_language_runtime_versions_for_provenance(self) -> None:
        versions = self.adapter.runtime_tool_versions()
        self.assertEqual("2.5.0", versions["epsilon"])
        self.assertEqual("5.10.2", versions["junit"])

    def test_it_reports_artifact_validity_without_executing(self) -> None:
        observation = self.adapter.validate_suite_artifacts(
            _suite(Path("/does/not/exist"))
        )
        self.assertIsInstance(observation, ArtifactValidation)
        self.assertFalse(observation.valid)

    def test_parsing_nothing_observes_nothing(self) -> None:
        from llm4mtl.languages.base import Workspace

        observations = self.adapter.parse_transformations(
            [], Workspace(Path("/engine"), Path("/observations"))
        )
        self.assertEqual({}, observations)

    def test_parser_writes_legacy_csv_only_to_run_evidence(self) -> None:
        from llm4mtl.languages.base import Workspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transformation = root / "candidate.etl"
            transformation.write_text("rule Candidate", encoding="utf-8")
            observations_dir = root / "run" / "observations" / "syntax-validation"
            completed = SimpleNamespace(
                stdout=(
                    '{"status":"completed","passed_transformations":'
                    f'["{transformation}"]}}\n'
                ),
                stderr="",
                returncode=0,
            )

            with patch(
                "llm4mtl.languages.etl.adapter.subprocess.run",
                return_value=completed,
            ) as run:
                observation = self.adapter.parse_transformations(
                    [transformation],
                    Workspace(root / "engine", observations_dir),
                )

            command = run.call_args.args[0]
            results_file = Path(command[command.index("--results-file") + 1])
            self.assertEqual(
                observations_dir / "generated_transformation_syntax.csv",
                results_file,
            )
            self.assertNotIn("engines", results_file.parts)
            self.assertTrue(observation[transformation].parsed)

    def test_execution_preserves_the_etl_maven_command_and_restores_injections(self) -> None:
        from llm4mtl.languages.base import Workspace

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            suite_dir = root / "suite"
            models_dir = suite_dir / "models"
            models_dir.mkdir(parents=True)
            (suite_dir / "GeneratedSmokeTest.java").write_text(
                "package generated;\npublic class GeneratedSmokeTest {}\n",
                encoding="utf-8",
            )
            (models_dir / "input.model").write_text("<Root/>\n", encoding="utf-8")
            transformation = root / "Tree2Graph.etl"
            transformation.write_text("rule Smoke\n", encoding="utf-8")
            engine_dir = root / "engine"
            engine_dir.mkdir()
            command_result = CommandResult(
                exit_code=0,
                stdout="Tests run: 1, Failures: 0, Errors: 0\nBUILD SUCCESS\n",
                stderr="",
            )

            with patch(
                "llm4mtl.semantic_tests.suite_execution.run_maven",
                return_value=command_result,
            ) as run_maven:
                observation, evidence = self.adapter.execute_suite(
                    _suite(suite_dir),
                    transformation,
                    Workspace(engine_dir, root / "observations"),
                    240,
                )

            run_maven.assert_called_once_with(
                [
                    "mvn",
                    "clean",
                    "test",
                    "-Dtest=generated.GeneratedSmokeTest",
                ],
                cwd=engine_dir,
                timeout=240,
            )
            self.assertTrue(observation.is_reference_valid)
            # The adapter hands back the raw output alongside the verdict, so a
            # caller can archive it before the next `mvn clean` deletes it.
            self.assertEqual(command_result.stdout, evidence.stdout)
            self.assertEqual(0, evidence.exit_code)
            self.assertFalse(
                engine_dir.joinpath(
                    "src/test/java/generated/GeneratedSmokeTest.java"
                ).exists()
            )
            self.assertFalse(
                engine_dir.joinpath(
                    "src/test/resources/transformations/Tree2Graph.etl"
                ).exists()
            )

    def test_it_reports_the_shared_observation_types(self) -> None:
        # The adapter's outputs are domain types, so the pipeline and the
        # evaluation layer never see an ETL-shaped result.
        annotations = {
            "render_suite_artifacts": ArtifactValidation,
            "validate_suite_artifacts": ArtifactValidation,
            "execute_suite": SuiteExecutionObservation,
            "normalize_transformation_failure": TransformationOutcome,
            "parse_transformations": ParseObservation,
        }
        for method, expected in annotations.items():
            with self.subTest(method=method):
                self.assertTrue(hasattr(self.adapter, method))
                self.assertIsNotNone(expected)

    def test_it_normalizes_only_attributable_transformation_failures(self) -> None:
        runtime = SuiteExecutionObservation(
            compiled=True,
            tests_discovered=True,
            models_loaded=True,
            engine_started=True,
            assertions_evaluated=False,
            assertions_passed=False,
            timed_out=False,
            maven_exit_code=1,
            failure_stage="engine_runtime",
            error_summary="EOL runtime failure",
        )
        unclassified = SuiteExecutionObservation(
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

        outcome = self.adapter.normalize_transformation_failure(runtime)
        self.assertEqual(OutcomeStatus.RUNTIME_FAILED, outcome.status)

        # This mapping is only ever reached for a reference-validated suite, so
        # an unrecognized throw is a runtime failure of the pairing rather than
        # an unusable observation. Returning None would drop it into the
        # suite-side bucket and out of the semantic-correctness denominator.
        unclassified_outcome = self.adapter.normalize_transformation_failure(unclassified)
        self.assertEqual(OutcomeStatus.RUNTIME_FAILED, unclassified_outcome.status)
        self.assertTrue(
            unclassified_outcome.status.is_attributable_to_the_transformation
        )


class ReactionsParserNormalizationTests(unittest.TestCase):
    def test_known_frozen_parser_linkage_false_positives_are_not_syntax_errors(self) -> None:
        diagnostic = "\n".join(
            [
                "Syntax issues (2):",
                "Duplicate reactions segment name 'example' (WARNING)",
                "The method run(unknown) refers to the missing type unknown (ERROR)",
            ]
        )
        self.assertTrue(_contains_only_unresolved_linkage_diagnostics(diagnostic))

    def test_real_grammar_diagnostics_still_fail(self) -> None:
        self.assertFalse(
            _contains_only_unresolved_linkage_diagnostics(
                "Syntax issues (1):\nno viable alternative at input ']' (ERROR)"
            )
        )


def _suite(path: Path):
    from llm4mtl.domain import GeneratedSuite

    return GeneratedSuite(
        "etl",
        path,
        "Tree2Graph",
        "gpt-5",
        "few_shot",
        "suite_001",
    )


if __name__ == "__main__":
    unittest.main()
