"""QVT-O implementation of the shared language adapter."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Sequence

from llm4mtl.conventions import QVTO_CONFIG, default_references_root, default_task_contracts_root
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
from llm4mtl.languages.qvto.rendering import render_qvto_test
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.suites.java import slug

PARSER_TIMEOUT_SECONDS = 900
PARSE_LINE = re.compile(r"LLM4MTL_PARSE\t(.+?)\t(\d+)")
PARSER_PROBE = """\
package org.qvto.parser;

import java.nio.file.Path;
import org.junit.jupiter.api.Test;

public class Llm4mtlParserProbeTest {
    @Test
    void parseRequestedFiles() throws Exception {
        String raw = System.getProperty("llm4mtl.files", "");
        for (String item : raw.split(java.io.File.pathSeparator)) {
            if (item.isBlank()) continue;
            QVTOParserFacade facade = new QVTOParserFacade();
            facade.parseFile(Path.of(item));
            System.out.println("LLM4MTL_PARSE\\t" + item + "\\t" + facade.getProblemCount());
        }
    }
}
"""


class QvtoAdapter:
    language_id = "qvto"
    renderer_version = "qvto-junit-v2"

    def __init__(
        self,
        references_root: Path | None = None,
        contracts_root: Path | None = None,
    ) -> None:
        self._references_root = references_root or default_references_root(QVTO_CONFIG)
        self._contracts_root = contracts_root or default_task_contracts_root(QVTO_CONFIG)

    def runtime_tool_versions(self) -> dict[str, str]:
        return {"qvto-harness": "1.0.0", "junit": "5.10.2"}

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
        project = workspace.engine_dir / "qvto-tests"
        actual = project / "actual"
        return execute_maven_suite(
            suite,
            transformation,
            workspace,
            timeout,
            transformation_destination=(
                actual / "src/main/resources/transformations" / f"{suite.task}.qvto"
            ),
            java_root=actual / "src/test/java",
            models_root=(
                actual
                / "src/test/resources/generated-models"
                / slug(suite.task)
            ),
            maven_cwd=project,
            maven_command=[
                "mvn",
                "clean",
                "test",
                "-pl",
                "actual",
                "-am",
                "-Dsurefire.failIfNoSpecifiedTests=false",
                "-Dtest={selectors}",
            ],
            reports_root=actual / "target/surefire-reports",
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
        probe = (
            parser_dir
            / "src/test/java/org/qvto/parser/Llm4mtlParserProbeTest.java"
        )
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text(PARSER_PROBE, encoding="utf-8")
        requested = os.pathsep.join(str(path.resolve()) for path in transformations)
        completed = subprocess.run(
            [
                "mvn",
                "-q",
                "-Dtest=Llm4mtlParserProbeTest",
                f"-Dllm4mtl.files={requested}",
                "test",
            ],
            cwd=parser_dir,
            capture_output=True,
            text=True,
            timeout=PARSER_TIMEOUT_SECONDS,
        )
        parsed = {
            Path(path).resolve(): int(problems)
            for path, problems in PARSE_LINE.findall(
                f"{completed.stdout}\n{completed.stderr}"
            )
        }
        return {
            path: ParseObservation(
                parsed=completed.returncode == 0 and parsed.get(path.resolve()) == 0,
                # No default: the probe prints one LLM4MTL_PARSE line per file it
                # actually parsed, so a path missing from that output was never
                # measured. Reporting 0 for it would claim the parser found no
                # problems in a transformation it never reached.
                problem_count=parsed.get(path.resolve()),
                diagnostic=(
                    ""
                    if completed.returncode == 0 and parsed.get(path.resolve()) == 0
                    else f"{completed.stdout}\n{completed.stderr}".strip()[-500:]
                ),
            )
            for path in transformations
        }
