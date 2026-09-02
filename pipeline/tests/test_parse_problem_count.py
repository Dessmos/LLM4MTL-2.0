"""A problem count the parser never reported is missing, not zero.

`errors_per_LOC` divides a problem count by the reference size. Substituting 0
for a transformation the parser never reached would report "no syntax problems
found" for exactly the runs where nothing was measured, and would pull the mean
towards zero in proportion to how often the parser failed.

`parsed` is a separate fact and is unchanged by any of this: a transformation
with no reported count is not parsed either way.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from llm4mtl.domain import ParseObservation
from llm4mtl.experiment_runner.adapters.transformation_parser import TransformationParserAdapter
from llm4mtl.experiment_runner.models import PipelineConfig
from llm4mtl.languages.base import Workspace
from llm4mtl.languages.qvto.adapter import QvtoAdapter
from llm4mtl.paths import REPO_ROOT


class QvtoProblemCountTests(unittest.TestCase):
    """The probe prints one LLM4MTL_PARSE line per file it actually parsed."""

    def observations(self, probe_output: str, *, returncode: int = 0):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            measured = root / "measured.qvto"
            missing = root / "missing.qvto"
            for path in (measured, missing):
                path.write_text("transformation x;\n", encoding="utf-8")
            completed = SimpleNamespace(
                stdout=probe_output.format(measured=measured.resolve()),
                stderr="",
                returncode=returncode,
            )
            with (
                patch(
                    "llm4mtl.languages.qvto.adapter.materialize_parser",
                    return_value=root / "parser",
                ),
                patch(
                    "llm4mtl.languages.qvto.adapter.subprocess.run",
                    return_value=completed,
                ),
            ):
                (root / "parser" / "src/test/java/org/qvto/parser").mkdir(parents=True)
                result = QvtoAdapter().parse_transformations(
                    [measured, missing],
                    Workspace(root / "engine", root / "observations"),
                )
            return result[measured], result[missing]

    def test_a_reported_zero_is_persisted_as_zero(self) -> None:
        measured, _ = self.observations("LLM4MTL_PARSE\t{measured}\t0\n")

        self.assertEqual(0, measured.problem_count)
        self.assertTrue(measured.parsed)

    def test_a_reported_count_is_persisted_verbatim(self) -> None:
        measured, _ = self.observations("LLM4MTL_PARSE\t{measured}\t7\n")

        self.assertEqual(7, measured.problem_count)
        self.assertFalse(measured.parsed)

    def test_a_transformation_the_parser_never_reported_has_no_count(self) -> None:
        _, missing = self.observations("LLM4MTL_PARSE\t{measured}\t0\n")

        self.assertIsNone(missing.problem_count)

    def test_a_missing_report_still_means_not_parsed(self) -> None:
        _, missing = self.observations("LLM4MTL_PARSE\t{measured}\t0\n")

        self.assertFalse(missing.parsed)

    def test_a_missing_report_is_never_confused_with_a_measured_zero(self) -> None:
        measured, missing = self.observations("LLM4MTL_PARSE\t{measured}\t0\n")

        self.assertEqual(0, measured.problem_count)
        self.assertIsNone(missing.problem_count)
        self.assertNotEqual(measured.problem_count, missing.problem_count)


class DefaultIsUnmeasuredTests(unittest.TestCase):

    def test_an_observation_that_states_no_count_reports_none(self) -> None:
        # ETL's parser driver reports pass/fail lists and no counts at all.
        self.assertIsNone(ParseObservation(parsed=False).problem_count)

    def test_a_stated_zero_is_kept(self) -> None:
        self.assertEqual(
            0, ParseObservation(parsed=True, problem_count=0).problem_count
        )


class SerializationTests(unittest.TestCase):
    """The stage's persisted evidence must keep the distinction readable."""

    def stage_details(
        self, observations: dict[Path, ParseObservation], paths: list[Path]
    ):
        adapter = TransformationParserAdapter(REPO_ROOT)
        config = PipelineConfig(
            language="qvto",
            tasks=["Mappings"],
            run_dir=str(REPO_ROOT / "artifacts" / "work"),
            engine_dir=str(REPO_ROOT),
        )
        with (
            patch.object(
                adapter.selector, "select_transformations", return_value=paths
            ),
            patch(
                "llm4mtl.experiment_runner.adapters.transformation_parser.language_adapter"
            ) as language,
        ):
            language.return_value.parse_transformations.return_value = observations
            return adapter.parse(config, dry_run=False).details

    def test_a_missing_count_serializes_as_null_never_zero(self) -> None:
        measured, missing = Path("/tmp/measured.qvto"), Path("/tmp/missing.qvto")
        details = self.stage_details(
            {
                measured: ParseObservation(parsed=True, problem_count=0),
                missing: ParseObservation(parsed=False, problem_count=None),
            },
            [measured, missing],
        )

        counts = details["problem_counts"]
        self.assertEqual(0, counts[str(measured)])
        self.assertIsNone(counts[str(missing)])

        serialized = json.loads(json.dumps(details))
        self.assertEqual(0, serialized["problem_counts"][str(measured)])
        self.assertIsNone(serialized["problem_counts"][str(missing)])

    def test_every_selected_transformation_appears_so_absence_is_visible(self) -> None:
        measured, missing = Path("/tmp/measured.qvto"), Path("/tmp/missing.qvto")
        details = self.stage_details(
            {
                measured: ParseObservation(parsed=True, problem_count=0),
                missing: ParseObservation(parsed=False, problem_count=None),
            },
            [measured, missing],
        )

        self.assertEqual({str(measured), str(missing)}, set(details["problem_counts"]))


if __name__ == "__main__":
    unittest.main()
