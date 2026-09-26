"""How the ATL, QVT-O and Reactions adapters inject a suite and call Maven.

Maven itself is replaced by a recorder, so these tests see exactly which files
sit in the run-local harness while Maven runs, and which command it gets.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm4mtl.domain import GeneratedSuite
from llm4mtl.external_tools.maven import CommandResult
from llm4mtl.languages import Workspace, language_adapter
from llm4mtl.semantic_tests.suite_execution import snapshot_dir

TASK = "Custom2Task"
LOCK_FILE = ".llm4mtl-execution.lock"
TEST_CLASS = "org.example.generated.CustomTest"

# Per language: the transformation file extension, the Maven working folder
# relative to the engine, the command before the observations option, and the
# files the harness holds while Maven runs.
EXPECTED = {
    "atl": (
        ".atl",
        ".",
        ["mvn", "clean", "test", f"-Dtest={TEST_CLASS}"],
        [
            f"src/main/atl/{TASK}.atl",
            "src/test/java/org/example/generated/CustomTest.java",
            "src/test/resources/generated-models/custom2task/nested/input.xmi",
        ],
    ),
    "qvto": (
        ".qvto",
        "qvto-tests",
        [
            "mvn",
            "clean",
            "test",
            "-pl",
            "actual",
            "-am",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            f"-Dtest={TEST_CLASS}",
        ],
        [
            f"qvto-tests/actual/src/main/resources/transformations/{TASK}.qvto",
            "qvto-tests/actual/src/test/java/org/example/generated/CustomTest.java",
            "qvto-tests/actual/src/test/resources/generated-models/custom2task/"
            "nested/input.xmi",
        ],
    ),
    "reactions": (
        ".reactions",
        ".",
        [
            "mvn",
            "clean",
            "test",
            "-pl",
            "vsum",
            "-am",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            f"-Dtest={TEST_CLASS}",
        ],
        [
            "consistency/pom.xml",
            "consistency/src/main/reactions/tools/vitruv/methodologisttemplate/"
            f"generated/{TASK}.reactions",
            "vsum/src/test/java/org/example/generated/CustomTest.java",
            "vsum/src/test/resources/generated-models/custom2task/nested/input.xmi",
        ],
    ),
}


class ExecuteMavenSuiteTests(unittest.TestCase):

    def test_suite_is_injected_run_once_and_removed_again(self) -> None:
        for language, (extension, cwd, command, injected) in EXPECTED.items():
            with self.subTest(language=language):
                with tempfile.TemporaryDirectory() as temp_dir:
                    root = Path(temp_dir)
                    calls, remaining = self._execute(root, language, extension)
                    engine = root / "engine"
                    suite = GeneratedSuite(
                        language, root / "suite", TASK, "gpt-5", "few_shot", "s1"
                    )
                    observations = snapshot_dir(root / "observations", suite)

                self.assertEqual(1, len(calls))
                self.assertEqual(
                    [*command, f"-Dllm4mtl.observations.dir={observations}"],
                    calls[0]["command"],
                )
                self.assertEqual((engine / cwd).resolve(), calls[0]["cwd"].resolve())
                self.assertEqual(60, calls[0]["timeout"])
                self.assertEqual(injected, calls[0]["files"])
                self.assertEqual([f for f in injected if f.endswith("pom.xml")], remaining)

    def _execute(
        self, root: Path, language: str, extension: str
    ) -> tuple[list[dict[str, object]], list[str]]:
        engine = root / "engine"
        engine.mkdir()
        if language == "reactions":
            # The adapter edits this pom before every run, so it must exist.
            (engine / "consistency").mkdir()
            (engine / "consistency/pom.xml").write_text(
                '<project xmlns="http://maven.apache.org/POM/4.0.0"/>',
                encoding="utf-8",
            )
        suite_dir = root / "suite"
        (suite_dir / "models/nested").mkdir(parents=True)
        (suite_dir / "CustomTest.java").write_text(
            "package org.example.generated;\n\npublic class CustomTest {}\n",
            encoding="utf-8",
        )
        (suite_dir / "models/nested/input.xmi").write_text("<xmi/>", encoding="utf-8")
        transformation = root / f"candidate{extension}"
        transformation.write_text("candidate", encoding="utf-8")
        suite = GeneratedSuite(language, suite_dir, TASK, "gpt-5", "few_shot", "s1")
        calls: list[dict[str, object]] = []

        def record(command: list[str], cwd: Path, timeout: int) -> CommandResult:
            calls.append(
                {
                    "command": command,
                    "cwd": cwd,
                    "timeout": timeout,
                    "files": _engine_files(engine),
                }
            )
            return CommandResult(exit_code=1, stdout="", stderr="BUILD FAILURE")

        with patch("llm4mtl.languages.common.run_maven", side_effect=record):
            language_adapter(language).execute_suite(
                suite,
                transformation,
                Workspace(engine_dir=engine, observations_dir=root / "observations"),
                60,
            )
        return calls, _engine_files(engine)


def _engine_files(engine: Path) -> list[str]:
    return sorted(
        path.relative_to(engine).as_posix()
        for path in engine.rglob("*")
        if path.is_file() and path.name != LOCK_FILE
    )


if __name__ == "__main__":
    unittest.main()
