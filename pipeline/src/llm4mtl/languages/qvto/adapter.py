"""QVT-O implementation of the shared language adapter."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import QVTO_CONFIG, default_references_root, default_task_contracts_root
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
    TEST_SELECTION_OPTION_PREFIX,
)
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.common import (
    ALLOW_MODULES_WITHOUT_SELECTED_TESTS,
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
from llm4mtl.languages.java_resources import java_text
from llm4mtl.languages.qvto.rendering import render_qvto_test
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.generated_models import generated_models_dir
from llm4mtl.semantic_tests.surefire import SUREFIRE_REPORTS_DIR

# Versions pinned by engines/qvto/harness/qvto-tests/pom.xml: the harness
# project's own version and its junit.version property.
QVTO_HARNESS_VERSION = "1.0.0"
JUNIT_VERSION = "5.10.2"

# The harness project and the module inside it that runs the suites.
HARNESS_PROJECT = "qvto-tests"
HARNESS_MODULE = "actual"

# A JUnit test copied into the parser project. It parses the requested files
# and prints one marker line per file, then one per problem found.
PROBE_CLASS = "Llm4mtlParserProbeTest"
PROBE_SOURCE = f"{PROBE_CLASS}.java.txt"
PROBE_DESTINATION = f"{MAVEN_TEST_JAVA_DIR}/org/qvto/parser/{PROBE_CLASS}.java"
PARSE_MARKER = "LLM4MTL_PARSE\t"
PROBLEM_MARKER = "LLM4MTL_PROBLEM\t"
PARSE_LINE = re.compile(PARSE_MARKER + r"(.+?)\t(\d+)")
# The probe prints each problem, not only the count: the count alone tells a
# refinement loop only that the file was rejected.
PROBLEM_LINE = re.compile(PROBLEM_MARKER + r"(.+?)\t(.+)")


class QvtoAdapter:
    language_id = "qvto"
    renderer_version = "qvto-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(QVTO_CONFIG)
        self._contracts_root = contracts_root or default_task_contracts_root(
            QVTO_CONFIG
        )

    def runtime_tool_versions(self) -> dict[str, str]:
        return {"qvto-harness": QVTO_HARNESS_VERSION, "junit": JUNIT_VERSION}

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        return render_generated_suite(
            task,
            extracted,
            language=self.language_id,
            config=QVTO_CONFIG,
            transformation_extension=".qvto",
            render_test=render_qvto_test,
        )

    def reference_transformation(self, task: str) -> Path:
        return self._references_root / f"{task}.qvto"

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
        project = workspace.engine_dir / HARNESS_PROJECT
        actual = project / HARNESS_MODULE
        harness = MavenHarness(
            transformation_destination=(
                actual / "src/main/resources/transformations" / f"{suite.task}.qvto"
            ),
            java_root=actual / MAVEN_TEST_JAVA_DIR,
            models_root=(
                actual / MAVEN_TEST_RESOURCES_DIR / generated_models_dir(suite.task)
            ),
            maven_cwd=project,
            maven_command=(
                "mvn",
                "clean",
                "test",
                "-pl",
                HARNESS_MODULE,
                "-am",
                ALLOW_MODULES_WITHOUT_SELECTED_TESTS,
                TEST_SELECTION_OPTION,
            ),
            reports_root=actual / SUREFIRE_REPORTS_DIR,
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
        completed = _run_probe(parser_dir, transformations)
        report = _ProbeReport.read(completed)
        return {path: report.observation(path) for path in transformations}


def _run_probe(
    parser_dir: Path,
    transformations: Sequence[Path],
) -> subprocess.CompletedProcess[str]:
    """Copy the probe test into the parser project and run it on every file."""
    probe = parser_dir / PROBE_DESTINATION
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text(java_text(__package__, PROBE_SOURCE), encoding="utf-8")
    requested = os.pathsep.join(str(path.resolve()) for path in transformations)
    return run_parser_command(
        [
            "mvn",
            "-q",
            f"{TEST_SELECTION_OPTION_PREFIX}{PROBE_CLASS}",
            f"-Dllm4mtl.files={requested}",
            "test",
        ],
        parser_dir,
    )


@dataclass(frozen=True)
class _ProbeReport:
    """What one probe run said about each requested file."""

    succeeded: bool
    problem_counts: dict[Path, int]
    problems: dict[Path, list[str]]
    # The output without any per-file marker lines.
    driver_output: str

    @classmethod
    def read(cls, completed: subprocess.CompletedProcess[str]) -> _ProbeReport:
        combined = combined_output(completed)
        problems: dict[Path, list[str]] = {}
        for path, problem in PROBLEM_LINE.findall(combined):
            problems.setdefault(Path(path).resolve(), []).append(problem)
        return cls(
            succeeded=completed.returncode == 0,
            problem_counts={
                Path(path).resolve(): int(count)
                for path, count in PARSE_LINE.findall(combined)
            },
            problems=problems,
            driver_output="\n".join(
                line
                for line in combined.splitlines()
                if not line.startswith((PARSE_MARKER, PROBLEM_MARKER))
            ).strip(),
        )

    def observation(self, path: Path) -> ParseObservation:
        return ParseObservation(
            parsed=self._is_parsed(path),
            # No default: a file with no LLM4MTL_PARSE line was never parsed,
            # so its count is unknown, not 0.
            problem_count=self.problem_counts.get(path.resolve()),
            diagnostic=self._diagnostic(path),
        )

    def _is_parsed(self, path: Path) -> bool:
        return self.succeeded and self.problem_counts.get(path.resolve()) == 0

    def _diagnostic(self, path: Path) -> str:
        """This file's parse problems, or else the tail of the driver output.

        The driver output never includes marker lines, so a file never quotes
        another file's syntax error. When the probe did not reach the file (a
        build or harness failure), the output describes that failure. When the
        output held only marker lines, the diagnostic is empty.
        """
        if self._is_parsed(path):
            return ""
        problems = self.problems.get(path.resolve())
        if problems:
            return "\n".join(problems)
        return diagnostic_tail(self.driver_output)
