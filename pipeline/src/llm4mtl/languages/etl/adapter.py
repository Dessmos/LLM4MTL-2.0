"""The ETL implementation of :class:`~llm4mtl.languages.base.LanguageAdapter`.

Everything ETL-specific the pipeline needs is reachable from here: where
reference transformations live, how a suite runs in the Epsilon harness through
Maven, and how the Epsilon parser is called.

The parser runs as a subprocess. Its driver prints a JSON report, which is read
as data instead of matching text with regular expressions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import (
    ETL_CONFIG,
    default_references_root,
    default_task_contracts_root,
)
from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    OutcomeStatus,
    ParseObservation,
    RawExecutionEvidence,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.domain.observations import FailureStage
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.common import (
    combined_output,
    diagnostic_tail,
    failed_for_every_file,
    materialize_parser,
    pom_properties,
    run_parser_command,
    validate_rendered_suite,
)
from llm4mtl.languages.etl.rendering import render_semantic_test
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suite_execution import execute_suite_against

PARSER_BUILD_COMMAND = ("mvn", "-q", "compile")
PARSER_DRIVER = "validate_etl_syntax.py"
# The driver also writes a per-file CSV; it is kept only as run evidence.
PARSER_RESULTS_FILE = "generated_transformation_syntax.csv"
DRIVER_COMPLETED = "completed"


def _completed_parse_observations(
    transformations: Sequence[Path],
    payload: dict[str, object],
) -> dict[Path, ParseObservation]:
    parsed_paths = {
        Path(str(item)).resolve() for item in payload.get("passed_transformations", [])
    }
    all_selected_passed = len(transformations) == int(
        payload.get("selected") or 0
    ) and len(transformations) == int(payload.get("passed") or 0)
    # Prefer the file's own Epsilon problems: a repair model learns nothing from
    # being told again that its file was rejected. The whole report is only a
    # fallback for a failed file the driver gave no problems for.
    reported = {
        Path(str(key)).resolve(): str(value)
        for key, value in (payload.get("diagnostics") or {}).items()
    }
    fallback = json.dumps(payload, ensure_ascii=False)
    observations: dict[Path, ParseObservation] = {}
    for path in transformations:
        parsed = all_selected_passed or path.resolve() in parsed_paths
        observations[path] = ParseObservation(
            parsed=parsed,
            diagnostic="" if parsed else reported.get(path.resolve()) or fallback,
        )
    return observations


class EtlAdapter:
    """ETL: Epsilon transformations executed through the Maven/JUnit harness."""

    language_id = "etl"
    renderer_version = "etl-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(ETL_CONFIG)
        self._contracts_root = contracts_root or default_task_contracts_root(ETL_CONFIG)

    def reference_transformation(self, task: str) -> Path:
        return self._references_root / f"{task}.etl"

    def runtime_tool_versions(self) -> dict[str, str]:
        """Versions fixed by the ETL harness template's Maven contract."""
        pom = TARGET.engine_harness(self.language_id) / "pom.xml"
        return pom_properties(
            pom,
            {
                "epsilon": "epsilon.version",
                "junit": "junit.version",
            },
        )

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        """Validate semantic cases and replace all LLM Java with ETL JUnit."""
        return render_generated_suite(
            task,
            extracted,
            language=self.language_id,
            config=ETL_CONFIG,
            transformation_extension=".etl",
            render_test=render_semantic_test,
        )

    def validate_suite_artifacts(self, suite: GeneratedSuite) -> ArtifactValidation:
        """Everything that disqualifies a suite without running Maven."""
        contract = self._contracts_root / f"{suite.task}.json"
        return validate_rendered_suite(suite, contract_exists=contract.is_file())

    def execute_suite(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        workspace: Workspace,
        timeout: int,
    ) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
        return execute_suite_against(
            suite,
            transformation,
            workspace.engine_dir,
            timeout,
            observations_root=workspace.observations_dir,
        )

    def normalize_transformation_failure(
        self,
        observation: SuiteExecutionObservation,
    ) -> TransformationOutcome | None:
        """Map ETL execution failures to a transformation outcome.

        Same as :func:`llm4mtl.languages.common.normalize_failure`, except that
        there is no ``java_compilation`` row: a Java compile failure maps to
        ``None``.
        """
        if observation.timed_out:
            return TransformationOutcome(
                status=OutcomeStatus.TIMED_OUT,
                diagnostic=observation.error_summary,
            )
        status = {
            FailureStage.TRANSFORMATION_PARSE: OutcomeStatus.PARSE_FAILED,
            FailureStage.MODEL_LOADING: OutcomeStatus.RUNTIME_FAILED,
            FailureStage.ENGINE_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
            FailureStage.UNCLASSIFIED_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
            FailureStage.INFRASTRUCTURE: OutcomeStatus.INFRASTRUCTURE_FAILED,
        }.get(observation.failure_stage)
        if status is None:
            return None
        return TransformationOutcome(
            status=status, diagnostic=observation.error_summary
        )

    def parse_transformations(
        self,
        transformations: Sequence[Path],
        workspace: Workspace,
    ) -> dict[Path, ParseObservation]:
        """Run the Epsilon parser driver and read its JSON report.

        ``problem_count`` stays unset (not measured). The driver writes per-file
        counts only to its CSV; the JSON report read here has pass/fail lists
        and totals. Reporting 0 would claim Epsilon found no problems in a file
        it may have rejected. See ``engines/etl/parser/validate_etl_syntax.py``.
        """
        if not transformations:
            return {}

        parser_dir = materialize_parser(
            TARGET.engine_parser(self.language_id),
            workspace,
            self.language_id,
        )
        build = run_parser_command(PARSER_BUILD_COMMAND, parser_dir)
        if build.returncode != 0:
            diagnostic = diagnostic_tail(combined_output(build))
            return failed_for_every_file(transformations, diagnostic)
        completed = run_parser_command(
            _driver_command(parser_dir, transformations, workspace), parser_dir
        )
        payload = _last_json_object(completed.stdout)
        if payload.get("status") != DRIVER_COMPLETED:
            diagnostic = str(
                payload.get("error")
                or completed.stderr.strip()
                or "parser driver failed"
            )
            return failed_for_every_file(transformations, diagnostic)
        return _completed_parse_observations(transformations, payload)


def _driver_command(
    parser_dir: Path,
    transformations: Sequence[Path],
    workspace: Workspace,
) -> list[str]:
    """The parser driver call, with a JSON report and the CSV in run evidence."""
    command = [sys.executable, str(parser_dir / PARSER_DRIVER)]
    for transformation in transformations:
        command.extend(("--transformation", str(transformation)))
    workspace.observations_dir.mkdir(parents=True, exist_ok=True)
    results_file = workspace.observations_dir / PARSER_RESULTS_FILE
    command.extend(("--results-file", str(results_file), "--output-format", "json"))
    return command


def _last_json_object(stdout: str) -> dict[str, object]:
    """The driver prints its JSON report last; anything before it is noise."""
    for line in reversed(stdout.strip().splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {}
