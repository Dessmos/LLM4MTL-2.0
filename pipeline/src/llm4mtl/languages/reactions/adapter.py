"""Reactions implementation of the shared language adapter."""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Sequence

from llm4mtl.conventions import (
    REACTIONS_CONFIG,
    default_reactions_metamodels_root,
    default_references_root,
    default_task_contracts_root,
)
from llm4mtl.domain import (
    ArtifactValidation,
    GeneratedSuite,
    ParseObservation,
    RawExecutionEvidence,
    SuiteExecutionObservation,
    TransformationOutcome,
)
from llm4mtl.domain.observations import FailureStage
from llm4mtl.external_tools.maven import (
    MAVEN_TEST_JAVA_DIR,
    MAVEN_TEST_RESOURCES_DIR,
    POM_NAMESPACE,
)
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.common import (
    ALLOW_MODULES_WITHOUT_SELECTED_TESTS,
    DIAGNOSTIC_MAX_CHARS,
    TEST_SELECTION_OPTION,
    MavenHarness,
    combined_output,
    diagnostic_tail,
    execute_maven_suite,
    failed_for_every_file,
    materialize_parser,
    normalize_failure,
    run_parser_command,
    validate_rendered_suite,
)
from llm4mtl.languages.reactions.prerequisites import (
    UnmergeableTransformationError,
    bind_segment,
    merge_reactions,
    prerequisite_tasks,
)
from llm4mtl.languages.reactions.rendering import render_reactions_test, segment_name
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.generated_models import generated_models_dir
from llm4mtl.semantic_tests.surefire import SUREFIRE_REPORTS_DIR

# Versions pinned by engines/reactions/harness/pom.xml: its vitruv.version
# property and its junit-jupiter-api dependency.
VITRUV_VERSION = "3.1.2"
JUNIT_VERSION = "5.13.2"

# Longer than the shared parser limit: the build packages a large jar.
PARSER_TIMEOUT_SECONDS = 1200
PARSER_BUILD_COMMAND = ("mvn", "-q", "-pl", "parser", "-am", "package", "-DskipTests")
PARSER_JAR_GLOB = "*-all.jar"

# The harness module that holds and runs the generated tests.
TEST_MODULE = "vsum"
# Where the transformation under test goes in the consistency module.
TRANSFORMATION_DIR = (
    "consistency/src/main/reactions/tools/vitruv/methodologisttemplate/generated"
)

# `ReactionsCli` prints this exact line for a run in which the parser returned
# issues; the number is the measured issue count.
SYNTAX_ISSUES = re.compile(r"Syntax issues \((\d+)\):")

# The exit code recorded for an execution refused before Maven was invoked.
# A string, so it can never be mistaken for a code Maven returned.
MAVEN_NOT_INVOKED = "not_invoked"


class ReactionsAdapter:
    language_id = "reactions"
    renderer_version = "reactions-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(
            REACTIONS_CONFIG
        )
        self._contracts_root = contracts_root or default_task_contracts_root(
            REACTIONS_CONFIG
        )

    def runtime_tool_versions(self) -> dict[str, str]:
        return {"vitruv": VITRUV_VERSION, "junit": JUNIT_VERSION}

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
        with TemporaryDirectory() as scratch:
            try:
                transformation = self._prepared_for_harness(
                    suite.task,
                    transformation,
                    Path(scratch),
                )
            except UnmergeableTransformationError as exc:
                return _unmergeable_transformation(str(exc))
            return self._execute(suite, transformation, workspace, timeout)

    def _prepared_for_harness(
        self,
        task: str,
        transformation: Path,
        scratch: Path,
    ) -> Path:
        """A scratch copy of the file under test, in the shape the harness runs.

        Its segment is named after the task, because the rendered test looks the
        transformation up by that name; other languages place the file at a
        fixed name instead. Without it, a generation that picks another name
        never runs, and one that picks the name of the harness's own example
        segment clashes with it.

        The reactions this task presupposes then join that segment. A virtual
        model accepts only one change propagation specification per metamodel
        pair, and a prerequisite uses the same pair as its task. They are
        context, not the artifact under test: without them the task's reaction
        finds no correspondence and produces nothing.
        """
        prepared = bind_segment(
            transformation.read_text(encoding="utf-8"), segment_name(task)
        )
        prerequisites = prerequisite_tasks(task)
        if prerequisites:
            prepared = merge_reactions(
                prepared,
                [
                    (self._references_root / f"{name}.reactions").read_text(
                        encoding="utf-8"
                    )
                    for name in prerequisites
                ],
            )
        destination = scratch / transformation.name
        destination.write_text(prepared, encoding="utf-8")
        return destination

    def _execute(
        self,
        suite: GeneratedSuite,
        transformation: Path,
        workspace: Workspace,
        timeout: int,
    ) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
        engine = workspace.engine_dir
        module = engine / TEST_MODULE
        harness = MavenHarness(
            transformation_destination=(
                engine / TRANSFORMATION_DIR / f"{suite.task}.reactions"
            ),
            java_root=module / MAVEN_TEST_JAVA_DIR,
            models_root=(
                module / MAVEN_TEST_RESOURCES_DIR / generated_models_dir(suite.task)
            ),
            maven_cwd=engine,
            maven_command=(
                "mvn",
                "clean",
                "test",
                "-pl",
                TEST_MODULE,
                "-am",
                ALLOW_MODULES_WITHOUT_SELECTED_TESTS,
                TEST_SELECTION_OPTION,
            ),
            reports_root=module / SUREFIRE_REPORTS_DIR,
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
        build = run_parser_command(
            PARSER_BUILD_COMMAND, parser_dir, PARSER_TIMEOUT_SECONDS
        )
        jars = sorted((parser_dir / "parser/target").glob(PARSER_JAR_GLOB))
        if build.returncode != 0 or not jars:
            diagnostic = diagnostic_tail(combined_output(build))
            return failed_for_every_file(transformations, diagnostic)
        workspace.observations_dir.mkdir(parents=True, exist_ok=True)
        return {
            transformation: _parse_one(
                parser_dir,
                jars[-1],
                transformation,
                workspace.observations_dir / f"reactions-{index:03d}.xmi",
            )
            for index, transformation in enumerate(transformations)
        }


def _parse_one(
    parser_dir: Path,
    jar: Path,
    transformation: Path,
    output: Path,
) -> ParseObservation:
    """Run the packaged ``ReactionsCli`` on one file, writing its XMI to ``output``."""
    completed = run_parser_command(
        [
            "java",
            "-jar",
            str(jar),
            str(transformation.resolve()),
            str(output),
            str(default_reactions_metamodels_root()),
        ],
        parser_dir,
        PARSER_TIMEOUT_SECONDS,
    )
    diagnostic = combined_output(completed).strip()
    succeeded = completed.returncode == 0 and output.is_file()
    return ParseObservation(
        parsed=succeeded or _contains_only_unresolved_linkage_diagnostics(diagnostic),
        problem_count=_reported_issue_count(diagnostic, completed, output),
        diagnostic="" if succeeded else diagnostic[:DIAGNOSTIC_MAX_CHARS],
    )


def _reported_issue_count(
    diagnostic: str,
    completed: subprocess.CompletedProcess[str],
    output: Path,
) -> int | None:
    """How many issues the Reactions parser reported, or ``None`` if it said nothing.

    ``ReactionsCli`` prints ``Syntax issues (N):`` and exits non-zero when the
    Xtext parser finds issues. It writes the XMI and exits 0 when there are
    none. Only these two cases measure a count; a build failure, crash, or
    timeout gives ``None``.

    The count does not depend on the ``parsed`` verdict. Issues that are known
    false positives are still counted, while ``parsed`` may still be true.
    """
    reported = SYNTAX_ISSUES.search(diagnostic)
    if reported:
        return int(reported.group(1))
    if completed.returncode == 0 and output.is_file():
        return 0
    return None


def _contains_only_unresolved_linkage_diagnostics(diagnostic: str) -> bool:
    """Whether every reported issue is a known false positive of the parser.

    The frozen standalone parser does not have the harness's generated EPackage
    classes on its classpath, so valid references report ``unknown`` parameter
    types. It also loads the file twice and warns about a duplicate segment.
    These are not grammar errors. Linking is checked later, when Maven compiles
    the run-local harness.
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
    return all(
        any(fragment in line for fragment in allowed_fragments) for line in lines
    )


def _unmergeable_transformation(
    diagnostic: str,
) -> tuple[SuiteExecutionObservation, RawExecutionEvidence]:
    """The observation for a transformation refused before Maven ran.

    The phase is ``transformation_parse`` because the engine never accepted
    the transformation. Nothing compiled or ran, so every progress flag is
    false, and the refusal message is stored as the only stderr.
    """
    observation = SuiteExecutionObservation(
        compiled=False,
        tests_discovered=False,
        models_loaded=False,
        engine_started=False,
        assertions_evaluated=False,
        assertions_passed=False,
        timed_out=False,
        maven_exit_code=MAVEN_NOT_INVOKED,
        failure_stage=FailureStage.TRANSFORMATION_PARSE,
        error_summary=diagnostic,
    )
    evidence = RawExecutionEvidence(
        exit_code=MAVEN_NOT_INVOKED,
        timed_out=False,
        stdout="",
        stderr=diagnostic,
        reports_present=False,
    )
    return observation, evidence


def _remove_unused_legacy_dependency(pom: Path) -> None:
    """Remove an unused, unpublished demo dependency from the run-local pom.

    The frozen harness declares the old SDQ families demo JAR, but its sources
    use the harness's own families metamodel, and the JAR is no longer
    published. The frozen template must not be edited, so only the run-local
    copy is changed.
    """
    namespace = POM_NAMESPACE
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
