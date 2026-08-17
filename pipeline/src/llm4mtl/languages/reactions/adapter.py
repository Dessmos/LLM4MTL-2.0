"""Reactions implementation of the shared language adapter."""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import (
    REACTIONS_CONFIG,
    default_references_root,
    default_task_contracts_root,
)
from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.languages.base import Workspace
from llm4mtl.semantic_tests.execution_evidence import RawExecutionEvidence
from llm4mtl.languages.common import (
    execute_maven_suite,
    materialize_parser,
    normalize_failure,
    validate_rendered_suite,
)
from llm4mtl.languages.reactions.rendering import render_reactions_test
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.java import slug

PARSER_TIMEOUT_SECONDS = 1200

# `ReactionsCli` prints this exact line for a run in which the parser returned
# issues; the number is the measured issue count.
SYNTAX_ISSUES = re.compile(r"Syntax issues \((\d+)\):")


class ReactionsAdapter:
    language_id = "reactions"
    renderer_version = "reactions-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(REACTIONS_CONFIG)
        self._contracts_root = contracts_root or default_task_contracts_root(REACTIONS_CONFIG)

    def runtime_tool_versions(self) -> dict[str, str]:
        return {"vitruv": "3.1.2", "junit": "5.13.2"}

    def render_suite_artifacts(
        self,
        task: str,
        extracted: dict[str, str],
    ) -> tuple[dict[str, str], ArtifactValidation]:
        return render_generated_suite(
            task,
            extracted,
            language=self.language_id,
            config=REACTIONS_CONFIG,
            transformation_extension=".reactions",
            render_test=render_reactions_test,
        )

    def reference_transformation(self, task: str) -> Path:
        return self._references_root / f"{task}.reactions"

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
        _remove_unused_legacy_dependency(workspace.engine_dir / "consistency/pom.xml")
        return execute_maven_suite(
            suite,
            transformation,
            workspace,
            timeout,
            transformation_destination=(
                workspace.engine_dir
                / "consistency/src/main/reactions/tools/vitruv/methodologisttemplate/generated"
                / f"{suite.task}.reactions"
            ),
            java_root=workspace.engine_dir / "vsum/src/test/java",
            models_root=(
                workspace.engine_dir
                / "vsum/src/test/resources/generated-models"
                / slug(suite.task)
            ),
            maven_cwd=workspace.engine_dir,
            maven_command=[
                "mvn",
                "clean",
                "test",
                "-pl",
                "vsum",
                "-am",
                "-Dsurefire.failIfNoSpecifiedTests=false",
                "-Dtest={selectors}",
            ],
            reports_root=workspace.engine_dir / "vsum/target/surefire-reports",
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
        build = subprocess.run(
            ["mvn", "-q", "-pl", "parser", "-am", "package", "-DskipTests"],
            cwd=parser_dir,
            capture_output=True,
            text=True,
            timeout=PARSER_TIMEOUT_SECONDS,
        )
        jars = sorted((parser_dir / "parser/target").glob("*-all.jar"))
        if build.returncode != 0 or not jars:
            diagnostic = f"{build.stdout}\n{build.stderr}".strip()[-500:]
            return {
                path: ParseObservation(parsed=False, diagnostic=diagnostic)
                for path in transformations
            }
        jar = jars[-1]
        ecores = TARGET.benchmark / "metamodels"
        workspace.observations_dir.mkdir(parents=True, exist_ok=True)
        observations: dict[Path, ParseObservation] = {}
        for index, transformation in enumerate(transformations):
            output = workspace.observations_dir / f"reactions-{index:03d}.xmi"
            completed = subprocess.run(
                [
                    "java",
                    "-jar",
                    str(jar),
                    str(transformation.resolve()),
                    str(output),
                    str(ecores),
                ],
                cwd=parser_dir,
                capture_output=True,
                text=True,
                timeout=PARSER_TIMEOUT_SECONDS,
            )
            diagnostic = f"{completed.stdout}\n{completed.stderr}".strip()
            syntax_valid = (
                completed.returncode == 0 and output.is_file()
            ) or _contains_only_unresolved_linkage_diagnostics(diagnostic)
            observations[transformation] = ParseObservation(
                parsed=syntax_valid,
                problem_count=_reported_issue_count(diagnostic, completed, output),
                diagnostic=(
                    ""
                    if completed.returncode == 0 and output.is_file()
                    else diagnostic[-500:]
                ),
            )
        return observations


def _reported_issue_count(
    diagnostic: str,
    completed: subprocess.CompletedProcess[str],
    output: Path,
) -> int | None:
    """How many issues the Reactions parser reported, or ``None`` if it said nothing.

    ``ReactionsCli`` prints ``Syntax issues (N):`` and exits non-zero whenever
    the Xtext parser returns issues, and writes the XMI and exits 0 when it
    returns none. Those are the only two states in which a count was measured;
    a build failure, a crash, or a timeout produces neither, and reporting a
    number for them would invent a measurement.

    This is deliberately independent of the syntax verdict. A run whose issues
    are all known false positives of the frozen standalone parser is still a run
    in which the parser counted them, so the count is reported as measured while
    ``parsed`` records the judgement.
    """
    reported = SYNTAX_ISSUES.search(diagnostic)
    if reported:
        return int(reported.group(1))
    if completed.returncode == 0 and output.is_file():
        return 0
    return None


def _contains_only_unresolved_linkage_diagnostics(diagnostic: str) -> bool:
    """Recognize false positives caused by the frozen standalone parser.

    The parser does not put the harness's generated EPackage classes on its
    classpath, so valid benchmark references report ``unknown`` routine
    parameter types. It also loads the requested resource twice and reports a
    duplicate segment warning. These are not grammar errors; Maven compilation
    in the run-local harness remains the semantic-link validation authority.
    """
    lines = [
        line.strip()
        for line in diagnostic.splitlines()
        if line.strip() and not line.startswith("Syntax issues (")
    ]
    if not lines:
        return False
    allowed_fragments = (
        "Duplicate reactions segment name",
        "refers to the missing type unknown",
        "The method or field affectedEObject is undefined",
    )
    return all(any(fragment in line for fragment in allowed_fragments) for line in lines)


def _remove_unused_legacy_dependency(pom: Path) -> None:
    """Remove an unavailable, unused demo artifact from the run-local copy.

    The frozen harness declares the old SDQ families demo JAR although its
    sources use the harness's own generated families metamodel. The artifact is
    no longer published. Editing the template is forbidden, so the adapter
    removes only that dependency from the isolated materialization.
    """
    namespace = "http://maven.apache.org/POM/4.0.0"
    tree = ET.parse(pom)
    root = tree.getroot()
    dependencies = root.find(f"{{{namespace}}}dependencies")
    if dependencies is None:
        return
    for dependency in list(dependencies):
        artifact = dependency.findtext(f"{{{namespace}}}artifactId")
        if artifact == "edu.kit.ipd.sdq.metamodels.families":
            dependencies.remove(dependency)
            ET.register_namespace("", namespace)
            tree.write(pom, encoding="UTF-8", xml_declaration=True)
            return
