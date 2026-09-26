from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from llm4mtl.paths import REPO_ROOT


sys.path.insert(0, str(REPO_ROOT))

from evaluation._common import EvaluationInputError
from evaluation.refinement_loops import (
    DONE,
    NOT_JUDGED,
    OVER_BUDGET,
    STOPPED,
    UNFINISHED,
    loop_rows,
    main,
    read_batch,
    summary_rows,
)


BATCH = "batch_001"
SYNTAX = "syntax-validation"
EXECUTION = "execution"


class LoopCellTests(unittest.TestCase):

    def test_run_solved_at_loop_one_is_done_afterwards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "solved", budget=3, attempts=[
                (SYNTAX, 0, "SYNTAX_VALID"),
                (EXECUTION, 0, "SEMANTIC_EXECUTION_FAILED"),
                (SYNTAX, 1, "SYNTAX_VALID"),
                (EXECUTION, 1, "SEMANTIC_PASSED"),
            ])

            [row] = loop_rows(read_batch(root, BATCH), 4)

        self.assertEqual(
            [row[f"loop_{loop}"] for loop in range(4)],
            ["SEMANTIC_EXECUTION_FAILED", "SEMANTIC_PASSED", DONE, DONE],
        )
        self.assertEqual(row["loops_needed"], 1)
        self.assertEqual(row["final_state"], "SEMANTIC_PASSED")

    def test_syntax_verdict_stands_when_execution_never_judged_the_iteration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "limit", budget=1, terminal_state="SYNTAX_INVALID:REFINEMENT_LIMIT_REACHED",
                       attempts=[(SYNTAX, 0, "SYNTAX_INVALID"), (SYNTAX, 1, "SYNTAX_INVALID")])

            [row] = loop_rows(read_batch(root, BATCH), 3)

        self.assertEqual(
            [row[f"loop_{loop}"] for loop in range(3)],
            ["SYNTAX_INVALID", "SYNTAX_INVALID", OVER_BUDGET],
        )
        self.assertEqual(row["loops_needed"], "")

    def test_latest_execution_of_an_iteration_wins_after_a_test_refinement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "retested", budget=1, attempts=[
                (SYNTAX, 0, "SYNTAX_VALID"),
                (EXECUTION, 0, "SEMANTIC_EXECUTION_FAILED"),
                (EXECUTION, 0, "SEMANTIC_PASSED"),
            ])

            [row] = loop_rows(read_batch(root, BATCH), 2)

        self.assertEqual([row["loop_0"], row["loop_1"]], ["SEMANTIC_PASSED", DONE])

    def test_run_whose_test_never_validated_is_kept_as_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "no-test", budget=1,
                       terminal_state="REFERENCE_VALIDATION_FAILED:REFINEMENT_LIMIT_REACHED", attempts=[])

            [row] = loop_rows(read_batch(root, BATCH), 3)

        self.assertEqual([row[f"loop_{loop}"] for loop in range(3)], [STOPPED, STOPPED, OVER_BUDGET])
        self.assertEqual(row["final_state"], "REFERENCE_VALIDATION_FAILED:REFINEMENT_LIMIT_REACHED")

    def test_gap_before_a_judged_iteration_is_not_judged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "gap", budget=2, attempts=[
                (SYNTAX, 0, "SYNTAX_INVALID"),
                (SYNTAX, 2, "SYNTAX_INVALID"),
            ])

            [row] = loop_rows(read_batch(root, BATCH), 3)

        self.assertEqual(row["loop_1"], NOT_JUDGED)

    def test_run_without_terminal_result_is_unfinished(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "running", budget=2, terminal_state=None,
                       attempts=[(SYNTAX, 0, "SYNTAX_INVALID")])

            [row] = loop_rows(read_batch(root, BATCH), 3)

        self.assertEqual([row["loop_1"], row["loop_2"]], [UNFINISHED, UNFINISHED])
        self.assertEqual(row["final_state"], UNFINISHED)


class LoopSummaryTests(unittest.TestCase):

    def test_solved_rate_counts_only_runs_known_at_each_loop(self) -> None:
        # Hand-calculated: A passes at 0; B passes at 2; C fails loops 0 and 1
        # and stops at its budget of 1; D never gets a judged transformation.
        # Known at 0: A B C (3), solved 1. Known at 1: A B C (3), solved 1.
        # Known at 2: A B (C is cut off by its budget), solved 2.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "a", budget=2, attempts=[(EXECUTION, 0, "SEMANTIC_PASSED")])
            _write_run(root, "b", budget=2, attempts=[
                (EXECUTION, 0, "SEMANTIC_EXECUTION_FAILED"),
                (EXECUTION, 1, "SEMANTIC_EXECUTION_FAILED"),
                (EXECUTION, 2, "SEMANTIC_PASSED"),
            ])
            _write_run(root, "c", budget=1, attempts=[
                (SYNTAX, 0, "SYNTAX_INVALID"),
                (SYNTAX, 1, "SYNTAX_INVALID"),
            ])
            _write_run(root, "d", budget=2, attempts=[])

            rows = summary_rows(read_batch(root, BATCH), 3)

        self.assertEqual(
            [(row["loop"], row["solved_within"], row["runs_known"], row["newly_solved"]) for row in rows],
            [(0, 1, 3, 1), (1, 1, 3, 0), (2, 2, 2, 1)],
        )
        self.assertEqual(rows[2]["solved_rate"], 1.0)
        self.assertEqual({(row["runs"], row["runs_without_verdict"]) for row in rows}, {(4, 1)})

    def test_different_strategies_get_their_own_groups_and_a_pooled_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "grammar", budget=0, strategy="grammar",
                       attempts=[(EXECUTION, 0, "SEMANTIC_PASSED")])
            _write_run(root, "few-shot", budget=0, strategy="few_shot",
                       attempts=[(EXECUTION, 0, "SEMANTIC_EXECUTION_FAILED")])

            rows = summary_rows(read_batch(root, BATCH), 1)

        self.assertEqual(
            [(row["transformation_strategy"], row["solved_within"], row["runs_known"]) for row in rows],
            [("few_shot", 0, 1), ("grammar", 1, 1), ("ALL", 1, 2)],
        )
        self.assertEqual(rows[2]["max_test_refinement_iterations"], "")


class LoopInputValidationTests(unittest.TestCase):

    def test_iteration_beyond_the_budget_fails_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "over", budget=0, attempts=[
                (SYNTAX, 0, "SYNTAX_INVALID"),
                (SYNTAX, 1, "SYNTAX_INVALID"),
            ])

            with self.assertRaisesRegex(EvaluationInputError, "over: judged transformation iteration 1 exceeds"):
                read_batch(root, BATCH)

    def test_attempt_that_cites_no_generation_fails_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_root = _write_run(root, "uncited", budget=0, attempts=[(SYNTAX, 0, "SYNTAX_INVALID")])
            result_path = run_root / "stages" / SYNTAX / "attempts" / "attempt-001" / "result.json"
            result_path.write_text(json.dumps({"outcome_code": "SYNTAX_INVALID", "artifacts": {}}), encoding="utf-8")

            with self.assertRaisesRegex(EvaluationInputError, "does not cite the transformation generation"):
                read_batch(root, BATCH)

    def test_run_filed_under_another_batch_fails_the_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "moved", budget=0, attempts=[], batch_id="batch_002")

            with self.assertRaisesRegex(EvaluationInputError, "manifest batch_id is 'batch_002'"):
                read_batch(root, BATCH)


class LoopReportFilesTests(unittest.TestCase):

    def test_main_writes_one_table_per_language_a_summary_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_run(root, "etl-run", budget=1, language="etl",
                       attempts=[(EXECUTION, 0, "SEMANTIC_PASSED")])
            _write_run(root, "atl-run", budget=1, language="atl",
                       attempts=[(SYNTAX, 0, "SYNTAX_INVALID"), (EXECUTION, 1, "SEMANTIC_PASSED")])
            output = root / "report"

            with redirect_stdout(io.StringIO()):
                exit_code = main(["--batch", BATCH, "--runs-root", str(root), "--output-dir", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                sorted(path.name for path in output.iterdir()),
                [
                    "refinement-loops-atl.csv",
                    "refinement-loops-etl.csv",
                    "refinement-loops-summary.csv",
                    "refinement-loops.md",
                ],
            )
            with (output / "refinement-loops-atl.csv").open(encoding="utf-8", newline="") as stream:
                [atl] = list(csv.DictReader(stream))
            markdown = (output / "refinement-loops.md").read_text(encoding="utf-8")

        self.assertEqual((atl["loop_0"], atl["loop_1"], atl["loops_needed"]), ("SYNTAX_INVALID", "SEMANTIC_PASSED", "1"))
        self.assertIn("## atl", markdown)
        self.assertIn("## etl", markdown)

    def test_main_reports_a_missing_batch_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "report"

            errors = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(errors):
                exit_code = main(["--batch", "batch_404", "--runs-root", str(root), "--output-dir", str(output)])

            self.assertEqual(exit_code, 1)
            self.assertIn("batch directory does not exist", errors.getvalue())
            self.assertFalse(output.exists())


def _write_run(
    root: Path,
    run_id: str,
    *,
    budget: int,
    attempts: list[tuple[str, int, str]],
    language: str = "reactions",
    strategy: str = "few_shots_AND_grammar",
    terminal_state: str | None = "SEMANTIC_PASSED",
    batch_id: str = BATCH,
) -> Path:
    run_root = root / BATCH / run_id
    run_root.mkdir(parents=True)
    manifest = {
        "run_id": run_id,
        "batch_id": batch_id,
        "language": language,
        "task": f"Task_{run_id}",
        "transformation_model": "gpt-5",
        "transformation_strategy": strategy,
        "seed": 1,
        "pipeline_variant": "full",
        "experiment_config": {
            "max_test_refinement_iterations": 1,
            "max_transformation_refinement_iterations": budget,
            "parser_feedback": True,
            "semantic_feedback": True,
            "source_diagnosis": True,
        },
    }
    (run_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if terminal_state is not None:
        terminal = {
            "run_id": run_id,
            "status": "completed",
            "terminal_state": terminal_state,
            "recorded_at": "2026-01-01T00:00:00+00:00",
            "test_iteration": 0,
        }
        (run_root / "result.json").write_text(json.dumps(terminal), encoding="utf-8")
    numbers: dict[str, int] = {}
    for stage, iteration, outcome in attempts:
        numbers[stage] = numbers.get(stage, 0) + 1
        attempt_dir = run_root / "stages" / stage / "attempts" / f"attempt-{numbers[stage]:03d}"
        attempt_dir.mkdir(parents=True)
        result = {
            "stage": stage,
            "outcome_code": outcome,
            "artifacts": {
                "transformation_generation_record":
                    f"generations/transformation/iteration-{iteration:03d}/generation.json",
            },
            "attempt": numbers[stage],
        }
        (attempt_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return run_root


if __name__ == "__main__":
    unittest.main()
