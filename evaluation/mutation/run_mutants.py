"""Qualify mutants and run baseline/generated suites against them offline.

``--batch`` is a second, separate mode: a task × mutant table for one batch.
For every run it takes the run's final generated suite (``suite_id`` in
``result.json``), runs it once on the task's reference and then on every mutant
of that task in ``evaluation/mutants/manifest.json``. Tasks have different
numbers of mutants; an operator that does not apply to a task is ``N/A``.

    KILLED        the suite passes on the reference and fails on the mutant
    SURVIVED      the suite passes on the reference and on the mutant
    PARSE_FAILED  the mutant does not parse, so the suite was not run
    ERROR         the suite could not execute on the mutant
    NOT_JUDGED    the suite does not pass on the reference (or the run has no
                  suite), so no mutant can be judged
    N/A           the operator does not apply to this task

``kill_rate`` is ``killed / mutants`` over the task's applicable mutants, blank
when nothing could be judged. It is a per-run reporting view, not ``MS_Q``:
there are no qualification suites here, so nothing is excluded as equivalent.

It must run in UTC, as the stage service container does: generated suites
compare dates as the JVM prints them in its default time zone, so elsewhere a
suite that passed in the pipeline can fail on the reference.

    TZ=UTC PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.mutation.run_mutants \
      --batch batch_004 --output evaluation/results/batch_004/mutants.csv
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    read_csv,
    read_json_object,
    write_csv,
)
from evaluation.mutation.generate_mutants import CATALOG_FIELDS
from evaluation.refinement_loops import read_batch
from llm4mtl.conventions import default_generated_tests_root, language_config
from llm4mtl.domain import GeneratedSuite, SuiteExecutionObservation
from llm4mtl.languages import Workspace, language_adapter
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.workspace import materialize_engine


OBSERVATION_FIELDS = (
    "mutant_id",
    "language",
    "task",
    "test_source",
    "test_id",
    "reference_result",
    "mutant_result",
    "killed",
)
TEST_SOURCES = frozenset({"qualification", "baseline", "generated"})
MUTANTS_MANIFEST = REPO_ROOT / "evaluation" / "mutants" / "manifest.json"
KILLED = "KILLED"
SURVIVED = "SURVIVED"
PARSE_FAILED = "PARSE_FAILED"
NOT_JUDGED = "NOT_JUDGED"
NOT_APPLICABLE = "N/A"
MATRIX_RUN_FIELDS = ("batch_id", "run_id", "language", "task", "suite_id", "reference_result")
MATRIX_COUNT_FIELDS = ("mutants", "killed", "survived", "kill_rate")


@dataclass(frozen=True)
class SuiteInput:
    """One independent qualification, baseline, or generated suite."""

    test_source: str
    test_id: str
    language: str
    task: str
    path: Path


def load_suite_inputs(path: Path) -> tuple[SuiteInput, ...]:
    suites: list[SuiteInput] = []
    seen: set[tuple[str, str]] = set()
    for line, row in enumerate(read_csv(path), start=2):
        source = row.get("test_source", "").strip().lower()
        test_id = row.get("test_id", "").strip()
        language = row.get("language", "").strip().lower()
        task = row.get("task", "").strip()
        suite_path = row.get("suite_path", "").strip()
        if source not in TEST_SOURCES:
            raise EvaluationInputError(
                f"{path}:{line}: test_source must be qualification, baseline, or generated"
            )
        if not all((test_id, language, task, suite_path)):
            raise EvaluationInputError(f"{path}:{line}: incomplete suite row")
        identity = (source, test_id)
        if identity in seen:
            raise EvaluationInputError(f"{path}:{line}: duplicate suite identity {identity}")
        seen.add(identity)
        resolved = Path(suite_path)
        if not resolved.is_absolute():
            resolved = REPO_ROOT / resolved
        if not resolved.is_dir():
            raise EvaluationInputError(f"{path}:{line}: suite directory not found: {resolved}")
        suites.append(SuiteInput(source, test_id, language, task, resolved.resolve()))
    if not suites:
        raise EvaluationInputError(f"suite input CSV is empty: {path}")
    task_keys = {(suite.language, suite.task) for suite in suites}
    for language, task in task_keys:
        present_sources = {
            suite.test_source
            for suite in suites
            if suite.language == language and suite.task == task
        }
        missing_sources = TEST_SOURCES - present_sources
        if missing_sources:
            raise EvaluationInputError(
                f"missing suite populations for {language}/{task}: "
                + ", ".join(sorted(missing_sources))
            )
    return tuple(suites)


def run_mutation_evaluation(
    catalog_rows: list[dict[str, str]],
    suite_inputs: Sequence[SuiteInput],
    timeout_seconds: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return qualified catalog rows and raw suite×mutant observations."""
    if timeout_seconds <= 0:
        raise EvaluationInputError("timeout_seconds must be positive")
    _validate_catalog(catalog_rows)
    qualified_catalog: list[dict[str, str]] = []
    observations: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="llm4mtl-mutation-") as temporary:
        root = Path(temporary)
        rendered_suites = {
            suite: _prepare_suite(suite, root / "suites" / str(index))
            for index, suite in enumerate(suite_inputs)
        }
        reference_cache: dict[SuiteInput, str] = {}
        workspaces: dict[str, Workspace] = {}
        for row in catalog_rows:
            language = row["language"].lower()
            task = row["task"]
            adapter = language_adapter(language)
            workspace = _language_workspace(language, root, workspaces)
            mutant = _resolve_catalog_path(row["mutant_path"])
            parse = adapter.parse_transformations([mutant], workspace)[mutant]
            matching_suites = [
                suite
                for suite in suite_inputs
                if suite.language == language and suite.task == task
            ]
            if not matching_suites:
                raise EvaluationInputError(
                    f"no suites configured for mutant {row['mutant_id']} ({language}/{task})"
                )
            qualification_mutant_results: list[str] = []
            qualification_kills: list[bool] = []
            for suite_input in matching_suites:
                suite = rendered_suites[suite_input]
                if suite_input not in reference_cache:
                    reference_observation, _ = adapter.execute_suite(
                        suite,
                        adapter.reference_transformation(task),
                        workspace,
                        timeout_seconds,
                    )
                    reference_cache[suite_input] = _execution_result(reference_observation)
                reference_result = reference_cache[suite_input]
                if parse.parsed:
                    mutant_observation, _ = adapter.execute_suite(
                        suite, mutant, workspace, timeout_seconds
                    )
                    mutant_result = _execution_result(mutant_observation)
                else:
                    mutant_result = "PARSE_FAILED"
                killed = reference_result == "PASS" and mutant_result == "FAIL"
                observations.append(
                    {
                        "mutant_id": row["mutant_id"],
                        "language": language,
                        "task": task,
                        "test_source": suite_input.test_source,
                        "test_id": suite_input.test_id,
                        "reference_result": reference_result,
                        "mutant_result": mutant_result,
                        "killed": str(killed).lower(),
                    }
                )
                if suite_input.test_source == "qualification":
                    qualification_mutant_results.append(mutant_result)
                    qualification_kills.append(killed)
            executable = any(
                outcome in {"PASS", "FAIL"}
                for outcome in qualification_mutant_results
            )
            observable = any(qualification_kills)
            qualified = parse.parsed and executable and observable
            qualified_catalog.append(
                {
                    **row,
                    "syntactic_validity": str(parse.parsed).lower(),
                    "executable": str(executable).lower(),
                    "observable": str(observable).lower(),
                    "qualified": str(qualified).lower(),
                }
            )
    return qualified_catalog, observations


def mutant_matrix(
    runs: Sequence[SelectedRun],
    mutants_manifest: Mapping[str, Any],
    timeout_seconds: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return the operator columns and one task × mutant row per run."""
    if timeout_seconds <= 0:
        raise EvaluationInputError("timeout_seconds must be positive")
    operators = sorted(mutants_manifest["operators"], key=lambda operator: int(operator.lstrip("M")))
    mutants_by_task: dict[tuple[str, str], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for entry in mutants_manifest["mutants"]:
        mutants_by_task[(entry["language"].lower(), entry["task"])][entry["mutant"]] = entry
    rows = []
    with tempfile.TemporaryDirectory(prefix="llm4mtl-mutant-matrix-") as temporary:
        root = Path(temporary)
        workspaces: dict[str, Workspace] = {}
        ordered = sorted(runs, key=lambda run: (run.language, run.task, run.run_id))
        for index, run in enumerate(ordered):
            task_mutants = mutants_by_task.get((run.language, run.task), {})
            applicable = {
                operator: entry
                for operator, entry in task_mutants.items()
                if entry.get("status") == "PRESENT"
            }
            reference_result, cells = _judge_run_mutants(
                run, applicable, root / "suites" / str(index), root, workspaces, timeout_seconds
            )
            killed = sum(cell == KILLED for cell in cells.values())
            judged = reference_result == "PASS" and bool(applicable)
            rows.append(
                {
                    "batch_id": run.manifest.get("batch_id", ""),
                    "run_id": run.run_id,
                    "language": run.language,
                    "task": run.task,
                    "suite_id": run.terminal_result.get("suite_id") or "",
                    "reference_result": reference_result,
                    **{operator: cells.get(operator, NOT_APPLICABLE) for operator in operators},
                    "mutants": len(applicable),
                    "killed": killed,
                    "survived": sum(cell == SURVIVED for cell in cells.values()),
                    "kill_rate": round(killed / len(applicable), 3) if judged else "",
                }
            )
    return operators, rows


def _judge_run_mutants(
    run: SelectedRun,
    applicable: Mapping[str, Mapping[str, Any]],
    suite_destination: Path,
    root: Path,
    workspaces: dict[str, Workspace],
    timeout_seconds: int,
) -> tuple[str, dict[str, str]]:
    """Run the run's final suite on the reference, then on every applicable mutant."""
    suite_id = run.terminal_result.get("suite_id")
    if not suite_id:
        return "NO_SUITE", {operator: NOT_JUDGED for operator in applicable}
    suite = _prepare_suite(
        SuiteInput("generated", suite_id, run.language, run.task, _generated_suite_path(run, suite_id)),
        suite_destination,
    )
    adapter = language_adapter(run.language)
    workspace = _language_workspace(run.language, root, workspaces)
    reference_observation, _ = adapter.execute_suite(
        suite, adapter.reference_transformation(run.task), workspace, timeout_seconds
    )
    reference_result = _execution_result(reference_observation)
    if reference_result != "PASS":
        return reference_result, {operator: NOT_JUDGED for operator in applicable}
    cells = {}
    for operator, entry in applicable.items():
        mutant = _resolve_catalog_path(entry["file"])
        if hashlib.sha256(mutant.read_bytes()).hexdigest() != entry.get("mutant_sha256"):
            raise EvaluationInputError(f"{mutant} does not match its mutant_sha256 in the manifest")
        if not adapter.parse_transformations([mutant], workspace)[mutant].parsed:
            cells[operator] = PARSE_FAILED
            continue
        observation, _ = adapter.execute_suite(suite, mutant, workspace, timeout_seconds)
        mutant_result = _execution_result(observation)
        cells[operator] = {"FAIL": KILLED, "PASS": SURVIVED}.get(mutant_result, mutant_result)
    return reference_result, cells


def _generated_suite_path(run: SelectedRun, suite_id: str) -> Path:
    candidates = default_generated_tests_root(language_config(run.language)) / run.task / "candidates"
    matches = sorted(path for path in candidates.glob(f"*/*/{suite_id}") if path.is_dir())
    if len(matches) != 1:
        raise EvaluationInputError(
            f"{run.run_id}: expected one generated suite {suite_id} under {candidates}, found {len(matches)}"
        )
    return matches[0]


def _language_workspace(language: str, root: Path, workspaces: dict[str, Workspace]) -> Workspace:
    workspace = workspaces.get(language)
    if workspace is None:
        engine_dir = materialize_engine(
            TARGET.engine_harness(language),
            root / "workspaces",
            f"{language}-harness",
        )
        workspace = Workspace(engine_dir, root / "observations" / language)
        workspaces[language] = workspace
    return workspace


def _prepare_suite(suite_input: SuiteInput, destination: Path) -> GeneratedSuite:
    adapter = language_adapter(suite_input.language)
    if (suite_input.path / "semantic_cases.json").is_file():
        extracted = {
            path.relative_to(suite_input.path).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(suite_input.path.rglob("*"))
            if path.is_file() and path.name != "metadata.json"
        }
        rendered, validation = adapter.render_suite_artifacts(suite_input.task, extracted)
        if not validation.valid:
            raise EvaluationInputError(
                f"suite {suite_input.test_id} is invalid: "
                + "; ".join(validation.violations)
            )
        for relative, content in rendered.items():
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
        (destination / "metadata.json").write_text(
            json.dumps({"artifact_validation": validation.as_metadata()}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        suite_path = destination
    else:
        suite_path = suite_input.path
    suite = GeneratedSuite(
        suite_input.language,
        suite_path,
        suite_input.task,
        suite_input.test_source,
        "offline-mutation",
        suite_input.test_id,
    )
    validation = adapter.validate_suite_artifacts(suite)
    if not validation.valid:
        raise EvaluationInputError(
            f"suite {suite_input.test_id} cannot execute: "
            + "; ".join(validation.violations)
        )
    return suite


def _execution_result(observation: SuiteExecutionObservation) -> str:
    if not observation.is_technically_executable:
        return "ERROR"
    return "PASS" if observation.assertions_passed else "FAIL"


def _resolve_catalog_path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        raise EvaluationInputError(f"mutant does not exist: {path}")
    return path.resolve()


def _validate_catalog(rows: list[dict[str, str]]) -> None:
    if not rows:
        raise EvaluationInputError("mutation catalog is empty")
    ids: set[str] = set()
    versions: set[str] = set()
    for row in rows:
        missing = [field for field in CATALOG_FIELDS[:9] if not row.get(field)]
        if missing:
            raise EvaluationInputError(
                f"catalog row misses fields: {', '.join(missing)}"
            )
        if row["mutant_id"] in ids:
            raise EvaluationInputError(f"duplicate mutant_id: {row['mutant_id']}")
        ids.add(row["mutant_id"])
        versions.add(row["operator_set_version"])
    if len(versions) != 1:
        raise EvaluationInputError("one evaluation cannot mix operator_set_version values")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--suites", type=Path)
    parser.add_argument("--qualified-catalog", type=Path)
    parser.add_argument("--batch", help="write the task × mutant table for this batch instead")
    parser.add_argument("--runs-root", type=Path, default=TARGET.runs)
    parser.add_argument("--mutants", type=Path, default=MUTANTS_MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.batch:
        return _write_mutant_matrix(args)
    if not (args.catalog and args.suites and args.qualified_catalog):
        parser.error("--catalog, --suites and --qualified-catalog are required without --batch")
    catalog_rows = read_csv(args.catalog)
    suite_inputs = load_suite_inputs(args.suites)
    qualified, observations = run_mutation_evaluation(
        catalog_rows, suite_inputs, args.timeout_seconds
    )
    write_csv(args.qualified_catalog, CATALOG_FIELDS, qualified)
    write_csv(args.output, OBSERVATION_FIELDS, observations)
    print(
        f"qualified {sum(row['qualified'] == 'true' for row in qualified)}/"
        f"{len(qualified)} mutants and wrote {args.output}"
    )
    return 0


def _write_mutant_matrix(args: argparse.Namespace) -> int:
    if time.tzname[0] != "UTC":
        print(f"error: run in UTC like the stage service (prefix TZ=UTC); local zone is {time.tzname[0]}", file=sys.stderr)
        return 1
    runs = [loops.run for loops in read_batch(args.runs_root, args.batch)]
    operators, rows = mutant_matrix(runs, read_json_object(args.mutants), args.timeout_seconds)
    write_csv(args.output, MATRIX_RUN_FIELDS + tuple(operators) + MATRIX_COUNT_FIELDS, rows)
    print(
        f"killed {sum(row['killed'] for row in rows)}/{sum(row['mutants'] for row in rows)} "
        f"mutants over {len(rows)} runs and wrote {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
