"""Tabulate what every transformation refinement loop produced, per language.

Loop 0 is the initially generated transformation, loop ``k`` its ``k``-th
refinement. Each cell is the verdict the pipeline itself recorded for that
transformation iteration: the latest ``execution`` attempt that judged it, or,
when it never reached execution, the latest ``syntax-validation`` attempt. The
verdict comes from the run's own generated test, not from a held-out suite.

A loop without a verdict says why:

    DONE          an earlier loop already passed, so the run ended there
    OVER_BUDGET   the loop lies beyond the run's transformation-refinement budget
    STOPPED       the run ended before this loop for another reason; the
                  ``final_state`` column names it (for example a test that never
                  passed on the reference, so no transformation was judged)
    NOT_JUDGED    a later loop was judged, but this one recorded no verdict
    UNFINISHED    the run has no terminal result yet

The summary answers how many loops are worth paying for: per loop ``k`` it counts
the runs solved within ``k`` loops over the runs whose state at ``k`` is known,
namely those that were judged at ``k`` or later, or had already passed. A run
cut off earlier by its budget or another stop is left out of loop ``k``'s
population instead of being counted as a failure. This is a reporting view like
``heldout-trajectory.csv``, not one of the campaign metrics.

Unlike the campaign preflight, runs whose transformation was never judged stay
in the table and in the ``runs`` count, so a batch is shown in full.

    PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.refinement_loops \
      --batch batch_007 --output-dir evaluation/results/batch_007

It writes ``refinement-loops-<language>.csv`` for every language,
``refinement-loops-summary.csv`` and a readable ``refinement-loops.md``.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    read_json_object,
    read_run_manifest,
    read_terminal_result,
    run_identity,
    write_csv,
)
from llm4mtl.paths import TARGET
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.stage_contract import SEMANTIC_PASSED
from llm4mtl.vocabulary import EXECUTION_STAGE_ID, SYNTAX_VALIDATION_STAGE_ID


DONE = "DONE"
OVER_BUDGET = "OVER_BUDGET"
STOPPED = "STOPPED"
NOT_JUDGED = "NOT_JUDGED"
UNFINISHED = "UNFINISHED"
ALL = "ALL"
# Execution judges an iteration only after its syntax validation, so for one
# iteration an execution attempt always outranks a syntax-validation attempt.
JUDGING_STAGES = (SYNTAX_VALIDATION_STAGE_ID, EXECUTION_STAGE_ID)
GENERATION_RECORD = re.compile(r"generations/transformation/iteration-(\d+)/generation\.json$")
RUN_FIELDS = (
    "batch_id",
    "run_id",
    "language",
    "task",
    "transformation_model",
    "transformation_strategy",
    "seed",
    "pipeline_variant",
    "max_test_refinement_iterations",
    "max_transformation_refinement_iterations",
    "parser_feedback",
    "semantic_feedback",
    "source_diagnosis",
    "test_iterations_used",
)
# The configuration a summary group must not mix. The transformation budget is
# absent on purpose: a smaller budget only shrinks the known population.
SUMMARY_GROUP_FIELDS = (
    "language",
    "transformation_model",
    "transformation_strategy",
    "pipeline_variant",
    "max_test_refinement_iterations",
    "parser_feedback",
    "semantic_feedback",
    "source_diagnosis",
)
SUMMARY_FIELDS = SUMMARY_GROUP_FIELDS + (
    "loop",
    "runs",
    "runs_without_verdict",
    "runs_known",
    "solved_within",
    "newly_solved",
    "solved_rate",
)
CELL_LABELS = {
    SEMANTIC_PASSED: "✅ PASSED",
    "SEMANTIC_EXECUTION_FAILED": "❌ SEMANTIC_FAILED",
    "SYNTAX_INVALID": "❌ SYNTAX_INVALID",
    "SYNTAX_VALID": "⚠️ SYNTAX_VALID, not executed",
    "INFRASTRUCTURE_ERROR": "⚠️ INFRASTRUCTURE_ERROR",
    DONE: "— done",
    OVER_BUDGET: "⛔ limit",
    STOPPED: "⛔ stopped",
    NOT_JUDGED: "? no verdict",
    UNFINISHED: "… unfinished",
}


@dataclass(frozen=True)
class RunLoops:
    """The recorded transformation verdicts of one run, by refinement loop."""

    batch_id: str
    run: SelectedRun
    is_finished: bool
    verdicts: Mapping[int, str]

    @property
    def transformation_budget(self) -> int:
        return int(self.run.manifest["experiment_config"]["max_transformation_refinement_iterations"])

    @property
    def solved_loop(self) -> int | None:
        """The loop whose transformation passed, or ``None`` when none did."""
        passed = [loop for loop, outcome in self.verdicts.items() if outcome == SEMANTIC_PASSED]
        return min(passed) if passed else None

    @property
    def last_judged_loop(self) -> int | None:
        return max(self.verdicts) if self.verdicts else None

    @property
    def width(self) -> int:
        """How many loop columns this run needs to be shown completely."""
        return max(self.transformation_budget, self.last_judged_loop or 0) + 1

    def cell(self, loop: int) -> str:
        if loop in self.verdicts:
            return self.verdicts[loop]
        solved = self.solved_loop
        if solved is not None and loop > solved:
            return DONE
        if loop > self.transformation_budget:
            return OVER_BUDGET
        last_judged = self.last_judged_loop
        if last_judged is not None and loop < last_judged:
            return NOT_JUDGED
        return STOPPED if self.is_finished else UNFINISHED

    def is_known_at(self, loop: int) -> bool:
        """True when it is recorded whether the run was solved within ``loop`` loops."""
        solved = self.solved_loop
        last_judged = self.last_judged_loop
        return (solved is not None and solved <= loop) or (
            last_judged is not None and last_judged >= loop
        )


def read_batch(runs_root: Path, batch_id: str) -> list[RunLoops]:
    """Read every run of one batch; fail listing every inconsistent run."""
    batch_root = runs_root / batch_id
    if not batch_root.is_dir():
        raise EvaluationInputError(f"batch directory does not exist: {batch_root}")
    runs: list[RunLoops] = []
    errors: list[str] = []
    for run_root in sorted(path for path in batch_root.iterdir() if path.is_dir()):
        try:
            runs.append(read_run_loops(batch_id, run_root))
        except EvaluationInputError as exc:
            errors.append(f"{run_root.name}: {exc}")
    if errors:
        raise EvaluationInputError(f"{batch_id} has inconsistent runs:\n- " + "\n- ".join(errors))
    if not runs:
        raise EvaluationInputError(f"batch {batch_id} contains no runs")
    return runs


def read_run_loops(batch_id: str, run_root: Path) -> RunLoops:
    manifest = read_run_manifest(run_root)
    if manifest.get("batch_id") != batch_id:
        raise EvaluationInputError(
            f"manifest batch_id is {manifest.get('batch_id')!r}, expected {batch_id!r}"
        )
    terminal = read_terminal_result(run_root)
    run = RunLoops(
        batch_id=batch_id,
        run=SelectedRun(run_root.name, run_root, manifest, terminal or {}),
        is_finished=terminal is not None,
        verdicts=_recorded_verdicts(RunPaths(run_root)),
    )
    _validate_loops(run)
    return run


def _recorded_verdicts(paths: RunPaths) -> dict[int, str]:
    """The outcome of the latest judging attempt of every transformation iteration."""
    latest: dict[int, tuple[tuple[int, int], str]] = {}
    for stage_rank, stage in enumerate(JUDGING_STAGES):
        for attempt in existing_attempts(paths.stage_attempts_dir(stage)):
            result_path = paths.stage_attempt_result(stage, attempt)
            # An attempt that crashed before writing its result judged nothing.
            if not result_path.is_file():
                continue
            result = read_json_object(result_path)
            loop = _judged_iteration(result, result_path)
            order = (stage_rank, attempt)
            if loop not in latest or order > latest[loop][0]:
                latest[loop] = (order, str(result.get("outcome_code")))
    return {loop: outcome for loop, (_, outcome) in latest.items()}


def _judged_iteration(result: Mapping[str, Any], result_path: Path) -> int:
    artifacts = result.get("artifacts")
    record = artifacts.get("transformation_generation_record") if isinstance(artifacts, dict) else None
    match = GENERATION_RECORD.search(record) if isinstance(record, str) else None
    if match is None:
        raise EvaluationInputError(
            f"{result_path} does not cite the transformation generation it judged"
        )
    return int(match.group(1))


def _validate_loops(run: RunLoops) -> None:
    last_judged = run.last_judged_loop
    if last_judged is not None and last_judged > run.transformation_budget:
        raise EvaluationInputError(
            f"judged transformation iteration {last_judged} exceeds the configured "
            f"budget {run.transformation_budget}"
        )
    solved = run.solved_loop
    if solved is not None and last_judged != solved:
        raise EvaluationInputError(
            f"transformation iteration {last_judged} was judged after iteration {solved} passed"
        )


def loop_rows(runs: Sequence[RunLoops], width: int) -> list[dict[str, Any]]:
    """One row per run with a ``loop_<k>`` cell for every loop below ``width``."""
    rows = []
    for run in sorted(runs, key=_run_order):
        solved = run.solved_loop
        rows.append(
            {
                **_run_fields(run),
                **{f"loop_{loop}": run.cell(loop) for loop in range(width)},
                "loops_needed": "" if solved is None else solved,
                "final_state": run.run.terminal_result.get("terminal_state", UNFINISHED),
            }
        )
    return rows


def summary_rows(runs: Sequence[RunLoops], width: int) -> list[dict[str, Any]]:
    """Per loop, runs solved within it over runs whose state at it is known.

    Every configuration gets its own rows; a final ``ALL`` group per language
    pools them and leaves the configuration fields empty.
    """
    groups: dict[tuple[str, ...], list[RunLoops]] = defaultdict(list)
    for run in runs:
        fields = _run_fields(run)
        groups[tuple(str(fields[field]) for field in SUMMARY_GROUP_FIELDS)].append(run)
    rows = []
    for key in sorted(groups):
        rows.extend(_group_summary(dict(zip(SUMMARY_GROUP_FIELDS, key)), groups[key], width))
    if len(groups) > 1:
        pooled = {field: "" for field in SUMMARY_GROUP_FIELDS}
        pooled.update(language=runs[0].run.language, transformation_model=ALL, transformation_strategy=ALL)
        rows.extend(_group_summary(pooled, runs, width))
    return rows


def _group_summary(
    group: Mapping[str, str],
    runs: Sequence[RunLoops],
    width: int,
) -> list[dict[str, Any]]:
    rows = []
    for loop in range(width):
        known = [run for run in runs if run.is_known_at(loop)]
        solved_within = sum(1 for run in known if run.solved_loop is not None and run.solved_loop <= loop)
        rows.append(
            {
                **group,
                "loop": loop,
                "runs": len(runs),
                "runs_without_verdict": sum(1 for run in runs if not run.verdicts),
                "runs_known": len(known),
                "solved_within": solved_within,
                "newly_solved": sum(1 for run in runs if run.solved_loop == loop),
                "solved_rate": "" if not known else solved_within / len(known),
            }
        )
    return rows


def _run_fields(run: RunLoops) -> dict[str, Any]:
    manifest = run.run.manifest
    return {
        **run_identity(run.run),
        "batch_id": run.batch_id,
        "transformation_model": manifest.get("transformation_model", ""),
        "transformation_strategy": manifest.get("transformation_strategy", ""),
        "seed": manifest.get("seed", ""),
        "test_iterations_used": run.run.terminal_result.get("test_iteration", ""),
    }


def _run_order(run: RunLoops) -> tuple[str, ...]:
    manifest = run.run.manifest
    return (
        run.run.task,
        str(manifest.get("transformation_strategy", "")),
        str(manifest.get("transformation_model", "")),
        run.batch_id,
        run.run.run_id,
    )


def render_markdown(runs_by_language: Mapping[str, Sequence[RunLoops]]) -> str:
    """A readable version of the same tables, one section per language."""
    lines = [
        "# Transformation refinement loops",
        "",
        "Loop 0 is the initial transformation, loop k its k-th refinement. A cell is",
        "the pipeline's own verdict for that iteration, judged by the run's generated test.",
        "",
        "- `— done`: an earlier loop already passed",
        "- `⛔ limit`: beyond the run's transformation-refinement budget",
        "- `⛔ stopped`: the run ended before this loop; see *Final state*",
        "- `? no verdict`: a later loop was judged, this one was not",
        "",
    ]
    for language, runs in sorted(runs_by_language.items()):
        width = _table_width(runs)
        lines += [f"## {language}", "", *_markdown_loop_table(runs, width), ""]
        lines += ["Solved within k loops, over runs whose state at loop k is known:", ""]
        lines += [*_markdown_summary_table(summary_rows(runs, width)), ""]
    return "\n".join(lines)


def _markdown_loop_table(runs: Sequence[RunLoops], width: int) -> list[str]:
    loops = [f"Loop {loop}" for loop in range(width)]
    header = ["Task", "Strategy", "Model", "Batch", "Budget", *loops, "Loops needed", "Final state"]
    lines = [_markdown_row(header), _markdown_row(["---"] * len(header))]
    for row in loop_rows(runs, width):
        cells = [CELL_LABELS.get(row[f"loop_{loop}"], row[f"loop_{loop}"]) for loop in range(width)]
        needed = "not solved" if row["loops_needed"] == "" else str(row["loops_needed"])
        lines.append(
            _markdown_row(
                [
                    row["task"],
                    row["transformation_strategy"],
                    row["transformation_model"],
                    row["batch_id"],
                    str(row["max_transformation_refinement_iterations"]),
                    *cells,
                    needed,
                    f"`{row['final_state']}`",
                ]
            )
        )
    return lines


def _markdown_summary_table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    # Groups can share strategy and model yet differ in configuration; name the
    # fields that differ so two such groups are not read as one.
    configuration_fields = [
        field
        for field in SUMMARY_GROUP_FIELDS[3:]
        if len({row[field] for row in rows if row["transformation_strategy"] != ALL}) > 1
    ]
    header = ["Strategy", "Model", "Loop", "Solved within", "Known", "Rate", "New at loop", "No verdict"]
    if configuration_fields:
        header.insert(2, "Configuration")
    lines = [_markdown_row(header), _markdown_row(["---"] * len(header))]
    for row in rows:
        rate = "–" if row["solved_rate"] == "" else f"{row['solved_rate']:.0%}"
        cells = [
            row["transformation_strategy"],
            row["transformation_model"],
            str(row["loop"]),
            str(row["solved_within"]),
            str(row["runs_known"]),
            rate,
            str(row["newly_solved"]),
            f"{row['runs_without_verdict']} of {row['runs']}",
        ]
        if configuration_fields:
            configuration = ", ".join(
                f"{field}={row[field]}" for field in configuration_fields if row[field] != ""
            )
            cells.insert(2, configuration)
        lines.append(_markdown_row(cells))
    return lines


def _markdown_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _table_width(runs: Sequence[RunLoops]) -> int:
    return max(run.width for run in runs)


def write_reports(runs: Sequence[RunLoops], output_dir: Path) -> list[Path]:
    """Write the per-language CSVs, the summary CSV and the Markdown report."""
    runs_by_language: dict[str, list[RunLoops]] = defaultdict(list)
    for run in runs:
        runs_by_language[run.run.language].append(run)
    written = []
    summary: list[dict[str, Any]] = []
    for language, language_runs in sorted(runs_by_language.items()):
        width = _table_width(language_runs)
        path = output_dir / f"refinement-loops-{language}.csv"
        fields = RUN_FIELDS + tuple(f"loop_{loop}" for loop in range(width)) + ("loops_needed", "final_state")
        write_csv(path, fields, loop_rows(language_runs, width))
        written.append(path)
        summary.extend(summary_rows(language_runs, width))
    summary_path = output_dir / "refinement-loops-summary.csv"
    write_csv(summary_path, SUMMARY_FIELDS, summary)
    markdown_path = output_dir / "refinement-loops.md"
    markdown_path.write_text(render_markdown(runs_by_language), encoding="utf-8")
    return [*written, summary_path, markdown_path]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--batch",
        action="append",
        required=True,
        help="batch id to include; repeat the option to combine batches",
    )
    parser.add_argument("--runs-root", type=Path, default=TARGET.runs)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if len(set(args.batch)) != len(args.batch):
        print("error: a batch is listed twice", file=sys.stderr)
        return 1
    try:
        runs = [run for batch_id in args.batch for run in read_batch(args.runs_root, batch_id)]
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for path in write_reports(runs, args.output_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
