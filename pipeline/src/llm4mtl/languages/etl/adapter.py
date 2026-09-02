"""The ETL implementation of :class:`~llm4mtl.languages.base.LanguageAdapter`.

Everything ETL-specific the pipeline depends on is reachable from here: where
reference transformations live, how a rendered suite is executed against the
Epsilon harness through Maven, and how the Epsilon parser is invoked.

The parser is an external Java tool, so it stays a subprocess — but its JSON
output is parsed as data rather than scraped from human-readable text, which is
what lets the pipeline report typed observations instead of regex matches.
"""

from __future__ import annotations

import json
import subprocess
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
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.languages.base import Workspace
from llm4mtl.semantic_tests.execution_evidence import RawExecutionEvidence
from llm4mtl.languages.common import (
    materialize_parser,
    pom_properties,
    validate_rendered_suite,
)
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.suite_execution import execute_suite_against
from llm4mtl.semantic_tests.surefire import UNCLASSIFIED_RUNTIME
from llm4mtl.semantic_tests.codegen.java import render_semantic_test
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite

PARSER_TIMEOUT_SECONDS = 900


def _failed_parse_observations(
    transformations: Sequence[Path],
    diagnostic: str,
) -> dict[Path, ParseObservation]:
    return {
        path: ParseObservation(parsed=False, diagnostic=diagnostic)
        for path in transformations
    }


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
    diagnostic = json.dumps(payload, ensure_ascii=False)
    observations: dict[Path, ParseObservation] = {}
    for path in transformations:
        parsed = all_selected_passed or path.resolve() in parsed_paths
        observations[path] = ParseObservation(
            parsed=parsed,
            diagnostic="" if parsed else diagnostic,
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
        """Everything that disqualifies a suite without running Maven.

        The checks are the shared ones. ETL used to reimplement them, which is
        how it ended up the one language that accepted a suite with no task
        contract behind it.
        """
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
        """Map ETL engine failures without inventing a semantic snapshot.

        Same contract as :func:`llm4mtl.languages.common.normalize_failure`: the
        suite is already reference-validated here, so an unrecognized throw is a
        runtime failure of this pairing rather than an unusable observation.
        """
        if observation.timed_out:
            return TransformationOutcome(
                status=OutcomeStatus.TIMED_OUT,
                diagnostic=observation.error_summary,
            )
        status = {
            "transformation_parse": OutcomeStatus.PARSE_FAILED,
            "engine_runtime": OutcomeStatus.RUNTIME_FAILED,
            UNCLASSIFIED_RUNTIME: OutcomeStatus.RUNTIME_FAILED,
            "infrastructure": OutcomeStatus.INFRASTRUCTURE_FAILED,
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

        Every observation leaves ``problem_count`` unset, which records it as
        unmeasured rather than as zero. The driver does compute a per-file count
        and writes it to its CSV, but its JSON report — the only thing read here
        — carries pass/fail lists and totals, not per-file counts. Reporting 0
        would state that Epsilon found no problems in files it may have rejected.
        See ``engines/etl/parser/validate_etl_syntax.py``.
        """
        if not transformations:
            return {}

        parser_dir = materialize_parser(
            TARGET.engine_parser(self.language_id),
            workspace,
            self.language_id,
        )
        build = subprocess.run(
            ["mvn", "-q", "compile"],
            cwd=parser_dir,
            capture_output=True,
            text=True,
            timeout=PARSER_TIMEOUT_SECONDS,
        )
        if build.returncode != 0:
            diagnostic = f"{build.stdout}\n{build.stderr}".strip()[-500:]
            return _failed_parse_observations(transformations, diagnostic)
        command = [sys.executable, str(parser_dir / "validate_etl_syntax.py")]
        for transformation in transformations:
            command.extend(("--transformation", str(transformation)))
        workspace.observations_dir.mkdir(parents=True, exist_ok=True)
        results_file = (
            workspace.observations_dir / "generated_transformation_syntax.csv"
        )
        command.extend(
            (
                "--results-file",
                str(results_file),
                "--output-format",
                "json",
            )
        )

        completed = subprocess.run(
            command,
            cwd=parser_dir,
            capture_output=True,
            text=True,
            timeout=PARSER_TIMEOUT_SECONDS,
        )
        payload = _last_json_object(completed.stdout)
        if payload.get("status") != "completed":
            diagnostic = str(
                payload.get("error")
                or completed.stderr.strip()
                or "parser driver failed"
            )
            return _failed_parse_observations(transformations, diagnostic)

        return _completed_parse_observations(transformations, payload)


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
