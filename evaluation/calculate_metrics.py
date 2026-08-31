"""Aggregate the eight frozen BA metrics from immutable and derived artifacts."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    parse_bool,
    preflight_runs,
    read_csv,
    read_json_object,
    write_csv,
)
from llm4mtl.conventions import default_generated_tests_root, language_config
from llm4mtl.paths import TARGET


FIELDNAMES = (
    "run_id",
    "language",
    "task",
    "pipeline_variant",
    "max_test_refinement_iterations",
    "max_transformation_refinement_iterations",
    "parser_feedback",
    "semantic_feedback",
    "source_diagnosis",
    "metric",
    "numerator",
    "denominator",
    "value",
    "unit",
)


def calculate_metrics(
    selected_runs: Sequence[SelectedRun],
    heldout_rows: list[dict[str, str]],
    mutation_catalog: list[dict[str, str]],
    mutation_rows: list[dict[str, str]],
    coverage_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Return metric rows with explicit populations and denominators."""
    metrics: list[dict[str, Any]] = []
    for selected_run in selected_runs:
        executable, reference_pass, generated = _suite_counts(selected_run)
        metrics.append(
            _run_metric(
                selected_run,
                "executability_rate",
                executable,
                generated,
                "generated_suite",
            )
        )
        metrics.append(
            _run_metric(
                selected_run,
                "reference_pass_rate",
                reference_pass,
                executable,
                "executable_generated_suite",
            )
        )
    heldout_by_run = _heldout_counts(selected_runs, heldout_rows)
    for selected_run in selected_runs:
        counts = heldout_by_run[selected_run.run_id]
        metrics.extend(
            (
                _run_metric(
                    selected_run,
                    "heldout_semantic_pass_rate",
                    counts["final_pass"],
                    1,
                    "final_transformation",
                ),
                _run_metric(
                    selected_run,
                    "heldout_repair_success_rate",
                    counts["repaired"],
                    counts["repair_eligible"],
                    "initially_failing_refined_transformation",
                ),
                _run_metric(
                    selected_run,
                    "regression_rate",
                    counts["regressions"],
                    counts["initial_pass_cases"],
                    "initially_passing_heldout_case",
                ),
            )
        )
    metrics.extend(_aggregate_heldout_metrics(heldout_by_run))
    metrics.extend(_mutation_metrics(mutation_catalog, mutation_rows))
    metrics.extend(_coverage_metrics(selected_runs, coverage_rows))
    return metrics


def _suite_counts(selected_run: SelectedRun) -> tuple[int, int, int]:
    config = language_config(selected_run.language)
    candidates_root = (
        default_generated_tests_root(config)
        / selected_run.task
        / "candidates"
    )
    candidates: dict[str, Mapping[str, Any]] = {}
    if candidates_root.is_dir():
        for metadata_path in sorted(candidates_root.glob("*/*/*/metadata.json")):
            metadata = read_json_object(metadata_path)
            suite_id = str(metadata.get("suite_id") or "")
            if (
                metadata.get("language") == selected_run.language
                and metadata.get("task") == selected_run.task
                and suite_id.startswith(selected_run.run_id + "_")
            ):
                candidates[suite_id] = metadata
    if not candidates:
        raise EvaluationInputError(
            f"no generated suites found for selected run {selected_run.run_id}"
        )
    observations: dict[str, Mapping[str, Any]] = {}
    observations_root = selected_run.root / "observations"
    if observations_root.is_dir():
        for path in sorted(observations_root.rglob("suite_execution.json")):
            if "generated_transformations" in path.parts:
                continue
            payload = read_json_object(path)
            transformation = payload.get("inputs", {}).get("transformation", {})
            if transformation.get("role") != "reference_transformation":
                continue
            suite_id = str(payload.get("suite_id") or "")
            if suite_id in observations:
                raise EvaluationInputError(
                    f"duplicate reference observation for {selected_run.run_id}/{suite_id}"
                )
            observations[suite_id] = payload.get("observation", {})
    executable = 0
    reference_pass = 0
    for suite_id in candidates:
        observation = observations.get(suite_id)
        if not isinstance(observation, Mapping):
            continue
        is_executable = observation.get("technically_executable") is True
        executable += int(is_executable)
        reference_pass += int(
            is_executable and observation.get("reference_valid") is True
        )
    return executable, reference_pass, len(candidates)


def _heldout_counts(
    selected_runs: Sequence[SelectedRun],
    rows: list[dict[str, str]],
) -> dict[str, dict[str, int]]:
    selected_ids = {run.run_id for run in selected_runs}
    grouped: dict[str, dict[int, dict[str, str]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for line, row in enumerate(rows, start=2):
        run_id = row.get("run_id", "")
        if run_id not in selected_ids:
            raise EvaluationInputError(
                f"held-out CSV line {line} references unselected run {run_id!r}"
            )
        try:
            iteration = int(row.get("iteration", ""))
        except ValueError as exc:
            raise EvaluationInputError(
                f"held-out CSV line {line} has invalid iteration"
            ) from exc
        test_id = row.get("test_id", "")
        result = row.get("result", "")
        if not test_id or result not in {"PASS", "FAIL", "ERROR", "NOT_RUN"}:
            raise EvaluationInputError(
                f"held-out CSV line {line} has invalid test_id/result"
            )
        if test_id in grouped[run_id][iteration]:
            raise EvaluationInputError(
                f"duplicate held-out observation for {run_id}/{iteration}/{test_id}"
            )
        grouped[run_id][iteration][test_id] = result
    counts: dict[str, dict[str, int]] = {}
    for selected_run in selected_runs:
        run_iterations = grouped.get(selected_run.run_id)
        if not run_iterations or 0 not in run_iterations:
            raise EvaluationInputError(
                f"held-out observations miss T0 for {selected_run.run_id}"
            )
        final_iteration = max(run_iterations)
        initial = run_iterations[0]
        final = run_iterations[final_iteration]
        if set(initial) != set(final):
            raise EvaluationInputError(
                f"held-out case population changed between T0 and Tfinal for "
                f"{selected_run.run_id}"
            )
        initial_pass = all(result == "PASS" for result in initial.values())
        final_pass = all(result == "PASS" for result in final.values())
        was_refined = final_iteration > 0
        counts[selected_run.run_id] = {
            "final_pass": int(final_pass),
            "repair_eligible": int(not initial_pass and was_refined),
            "repaired": int(not initial_pass and was_refined and final_pass),
            "initial_pass_cases": sum(result == "PASS" for result in initial.values()),
            "regressions": sum(
                initial[test_id] == "PASS" and final[test_id] == "FAIL"
                for test_id in initial
            ),
        }
    return counts


def _aggregate_heldout_metrics(
    counts_by_run: Mapping[str, Mapping[str, int]],
) -> list[dict[str, Any]]:
    return [
        _aggregate_metric(
            "heldout_semantic_pass_rate",
            sum(counts["final_pass"] for counts in counts_by_run.values()),
            len(counts_by_run),
            "final_transformation",
        ),
        _aggregate_metric(
            "heldout_repair_success_rate",
            sum(counts["repaired"] for counts in counts_by_run.values()),
            sum(counts["repair_eligible"] for counts in counts_by_run.values()),
            "initially_failing_refined_transformation",
        ),
        _aggregate_metric(
            "regression_rate",
            sum(counts["regressions"] for counts in counts_by_run.values()),
            sum(counts["initial_pass_cases"] for counts in counts_by_run.values()),
            "initially_passing_heldout_case",
        ),
    ]


def _mutation_metrics(
    catalog_rows: list[dict[str, str]],
    observation_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    catalog_ids = [row.get("mutant_id", "") for row in catalog_rows]
    if not catalog_ids or any(not mutant_id for mutant_id in catalog_ids):
        raise EvaluationInputError("qualified mutation catalog has an empty mutant_id")
    if len(set(catalog_ids)) != len(catalog_ids):
        raise EvaluationInputError("qualified mutation catalog has duplicate mutant_id values")
    qualified = {
        row["mutant_id"]
        for row in catalog_rows
        if parse_bool(row.get("qualified", ""), field="qualified")
    }
    generated_kills: set[str] = set()
    baseline_kills: set[str] = set()
    seen_generated: set[str] = set()
    seen_baseline: set[str] = set()
    for row in observation_rows:
        mutant_id = row.get("mutant_id", "")
        if mutant_id not in qualified:
            continue
        source = row.get("test_source", "")
        killed = parse_bool(row.get("killed", ""), field="killed")
        if source == "generated":
            seen_generated.add(mutant_id)
            if killed:
                generated_kills.add(mutant_id)
        elif source == "baseline":
            seen_baseline.add(mutant_id)
            if killed:
                baseline_kills.add(mutant_id)
    missing_generated = qualified - seen_generated
    missing_baseline = qualified - seen_baseline
    if missing_generated or missing_baseline:
        raise EvaluationInputError(
            "qualified mutants lack generated/baseline observations: "
            f"generated={sorted(missing_generated)}, baseline={sorted(missing_baseline)}"
        )
    incremental = generated_kills - baseline_kills
    denominator = len(qualified)
    return [
        _aggregate_metric(
            "qualified_mutation_score",
            len(generated_kills),
            denominator,
            "qualified_mutant",
        ),
        _aggregate_metric(
            "incremental_mutation_score",
            len(incremental),
            denominator,
            "qualified_mutant",
        ),
    ]


def _coverage_metrics(
    selected_runs: Sequence[SelectedRun],
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("run_id", "")].append(row)
    metrics: list[dict[str, Any]] = []
    for selected_run in selected_runs:
        run_rows = grouped.get(selected_run.run_id)
        if not run_rows:
            raise EvaluationInputError(
                f"coverage observations missing for {selected_run.run_id}"
            )
        eligible_sets = {
            frozenset(filter(None, row.get("eligible_eclasses", "").split(";")))
            for row in run_rows
        }
        if len(eligible_sets) != 1:
            raise EvaluationInputError(
                f"coverage denominator changed within run {selected_run.run_id}"
            )
        eligible = set(next(iter(eligible_sets)))
        covered = {
            type_name
            for row in run_rows
            for type_name in row.get("covered_eclasses", "").split(";")
            if type_name
        }
        metrics.append(
            _run_metric(
                selected_run,
                "metamodel_eclass_coverage",
                len(covered & eligible),
                len(eligible),
                "eligible_input_eclass",
            )
        )
    return metrics


def _run_metric(
    selected_run: SelectedRun,
    metric: str,
    numerator: int,
    denominator: int,
    unit: str,
) -> dict[str, Any]:
    config = selected_run.manifest["experiment_config"]
    return {
        "run_id": selected_run.run_id,
        "language": selected_run.language,
        "task": selected_run.task,
        "pipeline_variant": selected_run.manifest["pipeline_variant"],
        "max_test_refinement_iterations": config["max_test_refinement_iterations"],
        "max_transformation_refinement_iterations": config[
            "max_transformation_refinement_iterations"
        ],
        "parser_feedback": str(config["parser_feedback"]).lower(),
        "semantic_feedback": str(config["semantic_feedback"]).lower(),
        "source_diagnosis": str(config["source_diagnosis"]).lower(),
        "metric": metric,
        "numerator": numerator,
        "denominator": denominator,
        "value": "" if denominator == 0 else numerator / denominator,
        "unit": unit,
    }


def _aggregate_metric(
    metric: str,
    numerator: int,
    denominator: int,
    unit: str,
) -> dict[str, Any]:
    return {
        "run_id": "ALL",
        "language": "",
        "task": "",
        "pipeline_variant": "",
        "max_test_refinement_iterations": "",
        "max_transformation_refinement_iterations": "",
        "parser_feedback": "",
        "semantic_feedback": "",
        "source_diagnosis": "",
        "metric": metric,
        "numerator": numerator,
        "denominator": denominator,
        "value": "" if denominator == 0 else numerator / denominator,
        "unit": unit,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=TARGET.runs)
    parser.add_argument("--run-ids", type=Path, required=True)
    parser.add_argument("--heldout", type=Path, required=True)
    parser.add_argument("--mutation-catalog", type=Path, required=True)
    parser.add_argument("--mutation-results", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = preflight_runs(args.runs_root, args.run_ids)
    rows = calculate_metrics(
        selected,
        read_csv(args.heldout),
        read_csv(args.mutation_catalog),
        read_csv(args.mutation_results),
        read_csv(args.coverage),
    )
    write_csv(args.output, FIELDNAMES, rows)
    print(f"wrote {len(rows)} metric rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
