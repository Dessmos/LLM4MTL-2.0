"""ATL implementation of the shared language adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import ATL_CONFIG, default_references_root, default_task_contracts_root
from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    RawExecutionEvidence,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.external_tools.maven import (
    MAVEN_TEST_JAVA_DIR,
    MAVEN_TEST_RESOURCES_DIR,
)
from llm4mtl.languages.atl.rendering import render_atl_test
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.common import (
    TEST_SELECTION_OPTION,
    MavenHarness,
    combined_output,
    diagnostic_tail,
    execute_maven_suite,
    materialize_parser,
    normalize_failure,
    run_parser_command,
    validate_rendered_suite,
)
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.generated_models import generated_models_dir
from llm4mtl.semantic_tests.surefire import SUREFIRE_REPORTS_DIR

# Versions pinned by engines/atl/harness/pom.xml.
ATL_VERSION = "4.12.0"
JUNIT_VERSION = "5.9.3"

PARSE_RESULT = re.compile(r"RESULT:(OK|FAIL):(-?\d+)")
PARSE_OK = "OK"
# Compiles the parser and runs its main class; the file path is added last.
PARSER_COMMAND = (
    "mvn",
    "-q",
    "-DskipTests",
    "compile",
    "org.codehaus.mojo:exec-maven-plugin:3.1.0:java",
    "-Dexec.mainClass=com.example.atlparser.ATLParserMain",
)


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
        return {"atl": ATL_VERSION, "junit": JUNIT_VERSION}

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
        engine = workspace.engine_dir
        harness = MavenHarness(
            transformation_destination=engine / "src/main/atl" / f"{suite.task}.atl",
            java_root=engine / MAVEN_TEST_JAVA_DIR,
            models_root=(
                engine / MAVEN_TEST_RESOURCES_DIR / generated_models_dir(suite.task)
            ),
            maven_cwd=engine,
            maven_command=("mvn", "clean", "test", TEST_SELECTION_OPTION),
            reports_root=engine / SUREFIRE_REPORTS_DIR,
        )
        return execute_maven_suite(suite, transformation, workspace, timeout, harness)

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
        return {
            transformation: _parse_one(parser_dir, transformation)
            for transformation in transformations
        }


def _parse_one(parser_dir: Path, transformation: Path) -> ParseObservation:
    """Run ``ATLParserMain`` on one file and read its ``RESULT`` line."""
    completed = run_parser_command(
        [*PARSER_COMMAND, f"-Dexec.args={transformation.resolve()}"],
        parser_dir,
    )
    combined = combined_output(completed)
    match = PARSE_RESULT.search(combined)
    reported_ok = bool(match and match.group(1) == PARSE_OK)
    reported = int(match.group(2)) if match else None
    return ParseObservation(
        parsed=reported_ok and completed.returncode == 0,
        # `RESULT:FAIL:-1` means the file could not be parsed at all, so no
        # count exists, just as with a missing RESULT line. Only a value >= 0
        # is a measured count.
        problem_count=reported if reported is not None and reported >= 0 else None,
        diagnostic="" if reported_ok else diagnostic_tail(combined),
    )
