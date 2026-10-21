"""Report the held-out trajectory of every stored refinement iteration.

The frozen metrics compare ``T0 -> Tfinal`` and nothing else, because that is
the protocol the campaign is committed to. A refinement loop is far easier to
read when the intermediate iterations are visible as well, so this derived
report keeps one row per stored iteration.

It is deliberately a separate output. It consumes the same ``heldout.csv`` the
metrics consume and never changes a metric numerator, denominator, population,
or exclusion rule.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from evaluation._common import (
    RUN_IDENTITY_FIELDS,
    EvaluationInputError,
    SelectedRun,
    blank_identity,
    group_heldout_observations,
    preflight_runs,
    read_csv,
    run_identity,
    write_csv,
)
from llm4mtl.paths import TARGET


FIELDNAMES = RUN_IDENTITY_FIELDS + (
    "iteration",
    "is_initial",
    "is_final",
    "runs_in_cohort",
    "cases_total",
    "pass_count",
    "fail_count",
    "error_count",
    "not_run_count",
    "transformations_passing",
    "pass_rate",
    "repaired_since_previous",
    "regressed_since_previous",
    "repaired_since_initial",
    "regressed_since_initial",
)
COUNTED_FIELDS = (
    "cases_total",
    "pass_count",
    "fail_count",
    "error_count",
    "not_run_count",
    "transformations_passing",
    "repaired_since_previous",
    "regressed_since_previous",
    "repaired_since_initial",
    "regressed_since_initial",
)


def trajectory_rows(
    selected_runs: Sequence[SelectedRun],
    heldout_rows: Sequence[Mapping[str, str]],
) -> list[dict[str, Any]]:
    """Return one row per stored iteration, then one row per iteration cohort."""
    grouped = group_heldout_observations(selected_runs, heldout_rows)
    rows: list[dict[str, Any]] = []
    by_iteration: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for selected_run in selected_runs:
        iterations = grouped.get(selected_run.run_id)
        if not iterations:
            raise EvaluationInputError(
                f"held-out observations are missing for {selected_run.run_id}"
            )
        _validate_iterations(selected_run.run_id, iterations)
        for row in _run_rows(selected_run, iterations):
            rows.append(row)
            by_iteration[int(row["iteration"])].append(row)
    rows.extend(_cohort_rows(by_iteration))
    return rows


def _run_rows(
    selected_run: SelectedRun,
    iterations: Mapping[int, Mapping[str, str]],
) -> Iterator[dict[str, Any]]:
    numbers = sorted(iterations)
    final_iteration = numbers[-1]
    initial = iterations[0]
    for position, iteration in enumerate(numbers):
        results = iterations[iteration]
        previous = iterations[numbers[position - 1]] if position else None
        counts = Counter(results.values())
        total = len(results)
        yield {
            **run_identity(selected_run),
            "iteration": iteration,
            "is_initial": str(iteration == 0).lower(),
            "is_final": str(iteration == final_iteration).lower(),
            "runs_in_cohort": 1,
            "cases_total": total,
            "pass_count": counts["PASS"],
            "fail_count": counts["FAIL"],
            "error_count": counts["ERROR"],
            "not_run_count": counts["NOT_RUN"],
            "transformations_passing": int(
                total > 0 and counts["PASS"] == total
            ),
            "pass_rate": "" if total == 0 else counts["PASS"] / total,
            # An undefined step has no previous iteration to compare against, so
            # it stays blank rather than being reported as a zero-sized change.
            "repaired_since_previous": (
                "" if previous is None else _transitions(previous, results, "FAIL", "PASS")
            ),
            "regressed_since_previous": (
                "" if previous is None else _transitions(previous, results, "PASS", "FAIL")
            ),
            "repaired_since_initial": (
                "" if iteration == 0 else _transitions(initial, results, "FAIL", "PASS")
            ),
            "regressed_since_initial": (
                "" if iteration == 0 else _transitions(initial, results, "PASS", "FAIL")
            ),
        }


def _cohort_rows(
    by_iteration: Mapping[int, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Summarise each iteration over the runs that actually reached it.

    Runs that finished earlier are absent rather than carried forward, so
    ``runs_in_cohort`` is what keeps the shrinking population visible instead of
    hiding it inside an average.
    """
    rows: list[dict[str, Any]] = []
    for iteration in sorted(by_iteration):
        cohort = by_iteration[iteration]
        totals = {
            field: sum(int(row[field]) for row in cohort if row[field] != "")
            for field in COUNTED_FIELDS
        }
        cases_total = totals["cases_total"]
        rows.append(
            {
                **blank_identity(),
                "iteration": iteration,
                "is_initial": str(iteration == 0).lower(),
                # A cohort has no single final iteration: the runs inside it end
                # at different ones, and their own rows already say where.
                "is_final": "",
                "runs_in_cohort": len(cohort),
                **totals,
                "pass_rate": (
                    "" if cases_total == 0 else totals["pass_count"] / cases_total
                ),
                **(
                    {
                        field: ""
                        for field in (
                            "repaired_since_previous",
                            "regressed_since_previous",
                            "repaired_since_initial",
                            "regressed_since_initial",
                        )
                    }
                    if iteration == 0
                    else {}
                ),
            }
        )
    return rows


def _transitions(
    before: Mapping[str, str],
    after: Mapping[str, str],
    from_result: str,
    to_result: str,
) -> int:
    """Count cases that moved between two explicit outcomes.

    Only ``PASS`` and ``FAIL`` transitions are counted, matching the frozen
    regression definition. ``ERROR`` and ``NOT_RUN`` never become a silent
    assertion failure; they stay visible in the per-outcome counts instead.
    """
    return sum(
        1
        for test_id, result in before.items()
        if result == from_result and after.get(test_id) == to_result
    )


def _validate_iterations(
    run_id: str,
    iterations: Mapping[int, Mapping[str, str]],
) -> None:
    numbers = sorted(iterations)
    if numbers != list(range(len(numbers))):
        raise EvaluationInputError(
            f"held-out iterations for {run_id} must be contiguous from 0, found {numbers}"
        )
    expected = set(iterations[0])
    for iteration in numbers:
        if set(iterations[iteration]) != expected:
            raise EvaluationInputError(
                f"held-out case population changed at iteration {iteration} for {run_id}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=TARGET.runs)
    parser.add_argument("--run-ids", type=Path, required=True)
    parser.add_argument("--heldout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected_runs = preflight_runs(args.runs_root, args.run_ids)
    rows = trajectory_rows(selected_runs, read_csv(args.heldout))
    write_csv(args.output, FIELDNAMES, rows)
    print(f"wrote {len(rows)} trajectory rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
