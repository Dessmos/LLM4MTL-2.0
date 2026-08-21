"""One problem-count invariant, held by every language adapter.

    0     the parser measured zero problems
    N > 0 the parser measured N problems
    None  no measurement is available

`parsed` is a separate observation and none of this changes it: whether a
transformation is syntactically accepted is decided exactly as before.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from llm4mtl.conventions import default_reactions_metamodels_root
from llm4mtl.languages.atl.adapter import AtlAdapter
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.reactions.adapter import ReactionsAdapter


class AtlProblemCountTests(unittest.TestCase):
    """`ATLParserMain` prints RESULT:OK:0, RESULT:FAIL:N, or RESULT:FAIL:-1."""

    def observe(self, stdout: str, *, returncode: int = 0):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transformation = root / "candidate.atl"
            transformation.write_text("module x;\n", encoding="utf-8")
            completed = SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)
            with (
                patch(
                    "llm4mtl.languages.atl.adapter.materialize_parser",
                    return_value=root / "parser",
                ),
                patch(
                    "llm4mtl.languages.atl.adapter.subprocess.run", return_value=completed
                ),
            ):
                result = AtlAdapter().parse_transformations(
                    [transformation], Workspace(root / "engine", root / "observations")
                )
            return result[transformation]

    def test_a_measured_zero_is_kept(self) -> None:
        observation = self.observe("RESULT:OK:0\n")

        self.assertEqual(0, observation.problem_count)
        self.assertTrue(observation.parsed)

    def test_a_measured_count_is_kept(self) -> None:
        observation = self.observe("RESULT:FAIL:4\n", returncode=1)

        self.assertEqual(4, observation.problem_count)
        self.assertFalse(observation.parsed)

    def test_the_drivers_own_no_count_signal_is_not_a_zero(self) -> None:
        # ATLParserMain prints RESULT:FAIL:-1 when it could not parse at all.
        observation = self.observe("RESULT:FAIL:-1\n", returncode=1)

        self.assertIsNone(observation.problem_count)

    def test_output_without_a_result_line_has_no_count(self) -> None:
        observation = self.observe("[ERROR] the parser crashed\n", returncode=1)

        self.assertIsNone(observation.problem_count)

    def test_a_missing_count_still_means_not_parsed(self) -> None:
        for stdout, code in (("RESULT:FAIL:-1\n", 1), ("[ERROR] crash\n", 1)):
            with self.subTest(stdout=stdout):
                self.assertFalse(self.observe(stdout, returncode=code).parsed)


class ReactionsProblemCountTests(unittest.TestCase):
    """`ReactionsCli` prints `Syntax issues (N):` when the parser returns issues."""

    def observe(
        self,
        stderr: str,
        *,
        returncode: int = 0,
        write_output: bool = True,
        commands: list[list[str]] | None = None,
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transformation = root / "candidate.reactions"
            transformation.write_text("import x\n", encoding="utf-8")
            parser_dir = root / "parser"
            (parser_dir / "parser" / "target").mkdir(parents=True)
            (parser_dir / "parser" / "target" / "p-all.jar").write_text("", encoding="utf-8")
            build = SimpleNamespace(stdout="", stderr="", returncode=0)
            run = SimpleNamespace(stdout="", stderr=stderr, returncode=returncode)

            def fake_run(command, **_kwargs):
                if commands is not None:
                    commands.append(command)
                if command[0] == "mvn":
                    return build
                if write_output:
                    Path(command[4]).parent.mkdir(parents=True, exist_ok=True)
                    Path(command[4]).write_text("<xmi/>", encoding="utf-8")
                return run

            with (
                patch(
                    "llm4mtl.languages.reactions.adapter.materialize_parser",
                    return_value=parser_dir,
                ),
                patch(
                    "llm4mtl.languages.reactions.adapter.subprocess.run", side_effect=fake_run
                ),
            ):
                result = ReactionsAdapter().parse_transformations(
                    [transformation], Workspace(root / "engine", root / "observations")
                )
            return result[transformation]

    def test_a_clean_parse_is_a_measured_zero(self) -> None:
        observation = self.observe("")

        self.assertEqual(0, observation.problem_count)
        self.assertTrue(observation.parsed)

    def test_parser_loads_only_the_reactions_metamodel_corpus(self) -> None:
        commands: list[list[str]] = []

        self.observe("", commands=commands)

        java_command = next(command for command in commands if command[0] == "java")
        self.assertEqual(str(default_reactions_metamodels_root()), java_command[-1])

    def test_reported_issues_are_counted_not_collapsed_to_one(self) -> None:
        observation = self.observe(
            "Syntax issues (3):\nmissing token (ERROR)\nbad rule (ERROR)\noops (ERROR)\n",
            returncode=1,
            write_output=False,
        )

        self.assertEqual(3, observation.problem_count)
        self.assertFalse(observation.parsed)

    def test_a_run_that_reported_nothing_has_no_count(self) -> None:
        observation = self.observe(
            "Exception in thread \"main\" java.lang.OutOfMemoryError\n",
            returncode=1,
            write_output=False,
        )

        self.assertIsNone(observation.problem_count)
        self.assertFalse(observation.parsed)

    def test_the_count_is_reported_even_when_the_issues_are_known_false_positives(self) -> None:
        # The frozen standalone parser reports unresolved linkage that Maven
        # compilation later accepts. The verdict forgives them; the measurement
        # still records what the parser counted.
        observation = self.observe(
            "Syntax issues (2):\n"
            "Duplicate reactions segment name (WARNING)\n"
            "refers to the missing type unknown (ERROR)\n",
            returncode=1,
            write_output=False,
        )

        self.assertTrue(observation.parsed)
        self.assertEqual(2, observation.problem_count)

    def test_a_parser_build_failure_measures_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            transformation = root / "candidate.reactions"
            transformation.write_text("import x\n", encoding="utf-8")
            with (
                patch(
                    "llm4mtl.languages.reactions.adapter.materialize_parser",
                    return_value=root / "parser",
                ),
                patch(
                    "llm4mtl.languages.reactions.adapter.subprocess.run",
                    return_value=SimpleNamespace(stdout="", stderr="boom", returncode=1),
                ),
            ):
                result = ReactionsAdapter().parse_transformations(
                    [transformation], Workspace(root / "engine", root / "observations")
                )

            self.assertIsNone(result[transformation].problem_count)
            self.assertFalse(result[transformation].parsed)


if __name__ == "__main__":
    unittest.main()
