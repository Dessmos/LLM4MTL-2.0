"""How a path is written into an artifact, and where that is allowed to fail.

Every path the pipeline records is spelled the same way, because a recorded
path is read back and compared: a suite-execution observation is reused only
when its stored inputs equal the ones re-derived now, so two spellings of one
file would silently invalidate the observation and re-run Maven. There is one
rule, in two variants that differ only in what happens to a path outside the
repository — kept absolute, or refused.

These tests state the expected spelling literally rather than deriving it from
the functions, and they pin the boundary that turns the refusal into the
failure-report vocabulary.

The spelling is POSIX by construction (``as_posix``) rather than by whatever
``str`` would give. That is intent, not something these tests can prove: on the
only platform the engines run on the two are the same string, so no test here
can tell them apart. What the literal expectations below do pin is that the
separator is ``/`` and that the path is normalized before it is recorded.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from llm4mtl.paths import REPO_ROOT, repository_relative, require_repository_relative
from llm4mtl.semantic_tests.failure_report import FailureReportError
from llm4mtl.semantic_tests.failure_report.artifacts import _repository_path

INSIDE = {
    "a file": ("pipeline/src/llm4mtl/paths.py", "pipeline/src/llm4mtl/paths.py"),
    "a directory": ("benchmark/tasks/etl", "benchmark/tasks/etl"),
    "a deep artifact": (
        "artifacts/work/runs/r-1/stages/execution/attempts/attempt-001/result.json",
        "artifacts/work/runs/r-1/stages/execution/attempts/attempt-001/result.json",
    ),
    # Recorded paths are normalized, so two spellings of one file cannot make a
    # stored observation stop matching itself.
    "a path with dotted segments": (
        "pipeline/./src/../src/llm4mtl",
        "pipeline/src/llm4mtl",
    ),
    "a path containing a space": (
        "pipeline/src/llm4mtl/evaluation/etl/ETL Parser/run_parser.py",
        "pipeline/src/llm4mtl/evaluation/etl/ETL Parser/run_parser.py",
    ),
}
OUTSIDE = Path("/tmp/not-in-this-repository/run.json")


class RepositoryRelativeTests(unittest.TestCase):

    def test_a_path_inside_the_repository_is_written_relative_to_it(self) -> None:
        for name, (given, expected) in INSIDE.items():
            with self.subTest(path=name):
                self.assertEqual(expected, repository_relative(REPO_ROOT / given))

    def test_a_path_outside_the_repository_stays_absolute(self) -> None:
        """Never ``..``: a stored relative path would resolve against the reader."""
        recorded = repository_relative(OUTSIDE)
        self.assertTrue(Path(recorded).is_absolute())
        self.assertNotIn("..", recorded)


class RequireRepositoryRelativeTests(unittest.TestCase):

    def test_it_spells_an_inside_path_exactly_as_the_other_variant_does(self) -> None:
        for name, (given, expected) in INSIDE.items():
            with self.subTest(path=name):
                self.assertEqual(
                    expected, require_repository_relative(REPO_ROOT / given)
                )

    def test_it_refuses_a_path_outside_the_repository(self) -> None:
        with self.assertRaises(ValueError):
            require_repository_relative(OUTSIDE)


class FailureReportBoundaryTests(unittest.TestCase):

    def test_an_escaping_cited_path_becomes_the_package_error(self) -> None:
        """The assembler handles FailureReportError; a bare ValueError would escape."""
        with self.assertRaises(FailureReportError) as raised:
            _repository_path(OUTSIDE)
        self.assertIn("escapes the repository", str(raised.exception))

    def test_a_cited_path_inside_the_repository_is_spelled_the_same_way(self) -> None:
        self.assertEqual(
            "pipeline/pyproject.toml",
            _repository_path(REPO_ROOT / "pipeline/pyproject.toml"),
        )


if __name__ == "__main__":
    unittest.main()
