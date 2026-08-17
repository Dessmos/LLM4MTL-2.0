"""ATL implementation of the shared language adapter."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import ATL_CONFIG, default_references_root, default_task_contracts_root
from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.languages.atl.rendering import render_atl_test
from llm4mtl.languages.base import Workspace
from llm4mtl.semantic_tests.execution_evidence import RawExecutionEvidence
from llm4mtl.languages.common import (
    execute_maven_suite,
    materialize_parser,
    normalize_failure,
    validate_rendered_suite,
)
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.java import slug

PARSER_TIMEOUT_SECONDS = 900
PARSE_RESULT = re.compile(r"RESULT:(OK|FAIL):(-?\d+)")


class AtlAdapter:
    language_id = "atl"
    renderer_version = "atl-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(ATL_CONFIG)
        self._contracts_root = contracts_root or default_task_contracts_root(ATL_CONFIG)

    def runtime_tool_versions(self) -> dict[str, str]:
        return {"atl": "4.12.0", "junit": "5.9.3"}

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        return render_generated_suite(
            task,
            extracted,
            language=self.language_id,
            config=ATL_CONFIG,
            transformation_extension=".atl",
            render_test=render_atl_test,
        )

    def reference_transformation(self, task: str) -> Path:
        return self._references_root / f"{task}.atl"

    def validate_suite_artifacts(self, suite: GeneratedSuite) -> ArtifactValidation:
        contract = self._contracts_root / f"{suite.task}.json"
        return validate_rendered_suite(suite, contract_exists=contract.is_file())

    def execute_suite(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        workspace: Workspace,
        timeout: int,
    ) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
        return execute_maven_suite(
            suite,
            transformation,
            workspace,
            timeout,
            transformation_destination=workspace.engine_dir / "src/main/atl" / f"{suite.task}.atl",
            java_root=workspace.engine_dir / "src/test/java",
            models_root=(
                workspace.engine_dir
                / "src/test/resources/generated-models"
                / slug(suite.task)
            ),
            maven_cwd=workspace.engine_dir,
            maven_command=["mvn", "clean", "test", "-Dtest={selectors}"],
            reports_root=workspace.engine_dir / "target/surefire-reports",
        )

    def normalize_transformation_failure(
        self,
        observation: SuiteExecutionObservation,
    ) -> TransformationOutcome | None:
        return normalize_failure(observation)

    def parse_transformations(
        self,
        transformations: Sequence[Path],
        workspace: Workspace,
    ) -> dict[Path, ParseObservation]:
        if not transformations:
            return {}
        parser_dir = materialize_parser(
            TARGET.engine_parser(self.language_id),
            workspace,
            self.language_id,
        )
        observations: dict[Path, ParseObservation] = {}
        for transformation in transformations:
            completed = subprocess.run(
                [
                    "mvn",
                    "-q",
                    "-DskipTests",
                    "compile",
                    "org.codehaus.mojo:exec-maven-plugin:3.1.0:java",
                    "-Dexec.mainClass=com.example.atlparser.ATLParserMain",
                    f"-Dexec.args={transformation.resolve()}",
                ],
                cwd=parser_dir,
                capture_output=True,
                text=True,
                timeout=PARSER_TIMEOUT_SECONDS,
            )
            combined = f"{completed.stdout}\n{completed.stderr}"
            match = PARSE_RESULT.search(combined)
            reported = int(match.group(2)) if match else None
            observations[transformation] = ParseObservation(
                parsed=bool(match and match.group(1) == "OK" and completed.returncode == 0),
                # ATLParserMain prints `RESULT:FAIL:-1` when it could not parse
                # the file at all, so a negative value is its own signal that no
                # count exists — the same fact as a missing RESULT line. Only a
                # non-negative value was actually measured.
                problem_count=reported if reported is not None and reported >= 0 else None,
                diagnostic="" if match and match.group(1) == "OK" else combined.strip()[-500:],
            )
        return observations
