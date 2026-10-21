"""Compute every RQ1-RQ4 thesis metric from stored run artifacts."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import xml.etree.ElementTree as ElementTree
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable, Iterator, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    read_csv,
    read_json_object,
    read_run_manifest,
    read_terminal_result,
)
from llm4mtl.paths import TARGET


DEFAULT_SELECTION_ROOT = TARGET.artifacts / "Chosen_for_evaluation"
ALL_LANGUAGES = "ALL"
ALL_GROUPS = "ALL"

SUITE_VALID = "VALID"
SUITE_REFERENCE_INVALID = "REFERENCE_INVALID"
SUITE_NOT_EXECUTABLE = "NOT_EXECUTABLE"
SUITE_NO_VERDICT = "NO_VERDICT"

SYNTAX_REFINEMENT = "syntax_refinement"
SEMANTIC_REFINEMENT = "semantic_refinement"
TRANSFORMATION = "transformation"
SEMANTIC_TEST = "semantic-test"

CASE_PASS = "PASS"
CASE_FAIL = "FAIL"
CASE_ERROR = "ERROR"
CASE_SKIPPED = "SKIPPED"

KILLED = "KILLED"
SURVIVED = "SURVIVED"
NOT_APPLICABLE = "N/A"
REFERENCE_PASS = "PASS"
OPERATOR_COLUMN = re.compile(r"M\d+")

OUTPUT_FIELDS = (
    "rq",
    "metric",
    "role",
    "scope_type",
    "scope",
    "language",
    "category",
    "numerator",
    "denominator",
    "value",
    "note",
)

@dataclass(frozen=True)
class SuiteVerdict:
    """The reference execution of one generated suite iteration."""

    iteration: int
    state: str
    failure_stage: str


@dataclass(frozen=True)
class SyntaxVerdict:
    """The latest parser verdict for one transformation iteration."""

    iteration: int
    is_parsed: bool
    problem_count: int | None


@dataclass(frozen=True)
class Refinement:
    """One stored refinement and the execution attempt whose feedback drove it."""

    artifact_type: str
    purpose: str
    iteration: int
    is_noop: bool
    source_execution_attempt: int | None


@dataclass(frozen=True)
class Execution:
    """One semantic execution of a suite iteration on a transformation iteration."""

    attempt: int
    transformation_iteration: int
    suite_iteration: int
    is_passed: bool
    test_cases: Mapping[str, str] | None


@dataclass(frozen=True)
class RunFacts:
    """Everything the metrics need from one selected run."""

    group: str
    model: str
    run_id: str
    language: str
    suites: tuple[SuiteVerdict, ...]
    syntax: tuple[SyntaxVerdict, ...]
    refinements: tuple[Refinement, ...]
    executions: tuple[Execution, ...]
    final_transformation_iteration: int | None
    diagnoses: tuple[str, ...]
    mutant_row: Mapping[str, str] | None
    test_refinement_budget: int
    transformation_refinement_budget: int


@dataclass(frozen=True)
class EvaluationGroup:
    """One directory of the selection tree and the runs it selects."""

    name: str
    model: str
    runs: tuple[tuple[str, str], ...]
    mutant_rows: Mapping[str, Mapping[str, str]] | None

def discover_groups(selection_root: Path) -> tuple[EvaluationGroup, ...]:
    """Return every group below ``selection_root``, ordered by name."""
    groups = []
    for batch_runs in sorted(selection_root.rglob("batch-runs.csv")):
        group_dir = batch_runs.parent
        name = group_dir.relative_to(selection_root).as_posix()
        excluded = _read_excluded_run_ids(group_dir / "excluded-runs.txt")
        runs = tuple(
            (row["batch_id"], row["run_id"])
            for row in read_csv(batch_runs)
            if row["run_id"] not in excluded
        )
        if not runs:
            raise EvaluationInputError(f"{batch_runs} selects no runs")
        groups.append(
            EvaluationGroup(
                name=name,
                model=name.split("/", 1)[0],
                runs=runs,
                mutant_rows=_read_mutant_rows(group_dir),
            )
        )
    if not groups:
        raise EvaluationInputError(f"no batch-runs.csv below {selection_root}")
    return tuple(groups)


def _read_excluded_run_ids(path: Path) -> frozenset[str]:
    """Run ids of ``excluded-runs.txt`` lines shaped ``<batch>/<run-id>\\t<reason>``."""
    if not path.is_file():
        return frozenset()
    run_ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            run_ids.add(line.split("\t", 1)[0].strip().rsplit("/", 1)[-1])
    return frozenset(run_ids)


def _read_mutant_rows(group_dir: Path) -> dict[str, dict[str, str]] | None:
    files = sorted(group_dir.glob("mutants*.csv"))
    if not files:
        return None
    rows: dict[str, dict[str, str]] = {}
    for path in files:
        for row in read_csv(path):
            if row["run_id"] in rows:
                raise EvaluationInputError(f"run {row['run_id']} appears twice in {group_dir} mutant results")
            rows[row["run_id"]] = row
    return rows


def read_run_facts(group: EvaluationGroup, batch_id: str, run_id: str) -> RunFacts:
    """Collect the facts of one run, failing loudly on incomplete artifacts."""
    run_root = TARGET.run_dir(batch_id, run_id)
    try:
        manifest = read_run_manifest(run_root)
        if read_terminal_result(run_root) is None:
            raise EvaluationInputError("result.json is missing")
        transformation_records = _generation_records(run_root, TRANSFORMATION)
        facts = RunFacts(
            group=group.name,
            model=group.model,
            run_id=run_id,
            language=str(manifest["language"]),
            suites=_read_suites(run_root, run_id, str(manifest["task"])),
            syntax=_read_syntax(run_root),
            refinements=_read_refinements(run_root),
            executions=_read_executions(run_root, run_id),
            final_transformation_iteration=max(transformation_records, default=None),
            diagnoses=_read_diagnoses(batch_id, run_id),
            mutant_row=None if group.mutant_rows is None else group.mutant_rows.get(run_id),
            test_refinement_budget=int(manifest["experiment_config"]["max_test_refinement_iterations"]),
            transformation_refinement_budget=int(
                manifest["experiment_config"]["max_transformation_refinement_iterations"]
            ),
        )
    except EvaluationInputError as exc:
        raise EvaluationInputError(f"{batch_id}/{run_id}: {exc}") from exc
    if group.mutant_rows is not None and facts.mutant_row is None:
        raise EvaluationInputError(f"{batch_id}/{run_id}: no row in the mutant results of {group.name}")
    return facts


def _generation_records(run_root: Path, artifact_type: str) -> dict[int, dict]:
    records = {}
    for path in sorted((run_root / "generations" / artifact_type).glob("iteration-*/generation.json")):
        records[_number_suffix(path.parent.name)] = read_json_object(path)
    return records


def _read_suites(run_root: Path, run_id: str, task: str) -> tuple[SuiteVerdict, ...]:
    observations = {}
    for path in run_root.glob(f"observations/{task}/*/*/*/suite_execution.json"):
        suite_id = path.parent.name
        if not suite_id.startswith(f"{run_id}_"):
            raise EvaluationInputError(f"suite {suite_id} does not belong to the run")
        observations[_number_suffix(suite_id)] = read_json_object(path)["observation"]
    verdicts = []
    for iteration in sorted(_generation_records(run_root, SEMANTIC_TEST)):
        observation = observations.get(iteration)
        if observation is None:
            verdicts.append(SuiteVerdict(iteration, SUITE_NO_VERDICT, ""))
        elif not observation["technically_executable"]:
            verdicts.append(SuiteVerdict(iteration, SUITE_NOT_EXECUTABLE, observation["failure_stage"]))
        elif not observation["reference_valid"]:
            verdicts.append(SuiteVerdict(iteration, SUITE_REFERENCE_INVALID, observation["failure_stage"]))
        else:
            verdicts.append(SuiteVerdict(iteration, SUITE_VALID, ""))
    return tuple(verdicts)


def _read_syntax(run_root: Path) -> tuple[SyntaxVerdict, ...]:
    latest: dict[int, SyntaxVerdict] = {}
    for result, evidence in _stage_attempts(run_root, "syntax-validation"):
        iteration = _record_iteration(result, "transformation_generation_record")
        problem_counts = evidence.get("details", {}).get("problem_counts")
        problem_count = None
        if problem_counts and all(isinstance(count, int) for count in problem_counts.values()):
            problem_count = sum(problem_counts.values())
        latest[iteration] = SyntaxVerdict(iteration, result["status"] == "passed", problem_count)
    return tuple(latest[iteration] for iteration in sorted(latest))


def _read_refinements(run_root: Path) -> tuple[Refinement, ...]:
    refinements = []
    for artifact_type in (TRANSFORMATION, SEMANTIC_TEST):
        for iteration, record in sorted(_generation_records(run_root, artifact_type).items()):
            purpose = record.get("purpose")
            if iteration == 0 or not purpose:
                continue
            request = record.get("refinement_request")
            source_attempt = None
            if request and (run_root / request["path"]).is_file():
                source_attempt = read_json_object(run_root / request["path"]).get("execution_attempt")
            refinements.append(
                Refinement(
                    artifact_type=artifact_type,
                    purpose=purpose,
                    iteration=iteration,
                    is_noop=record["input_artifact"]["sha256"] == record["output_artifact"]["sha256"],
                    source_execution_attempt=source_attempt,
                )
            )
    return tuple(refinements)


def _read_executions(run_root: Path, run_id: str) -> tuple[Execution, ...]:
    executions = []
    for attempt, (result, evidence) in enumerate(_stage_attempts(run_root, "execution"), start=1):
        pairs = evidence.get("details", {}).get("pairs", [])
        if len(pairs) != 1:
            raise EvaluationInputError(f"execution attempt {attempt} has {len(pairs)} suite/transformation pairs")
        pair = pairs[0]
        executions.append(
            Execution(
                attempt=int(result.get("attempt", attempt)),
                transformation_iteration=_record_iteration(result, "transformation_generation_record"),
                suite_iteration=_record_iteration(result, "semantic_test_generation_record"),
                is_passed=bool(pair["assertions_passed"]),
                test_cases=_read_test_cases(_path_in_run(run_root, run_id, pair["evidence"]).parent),
            )
        )
    return tuple(executions)


def _read_test_cases(observation_dir: Path) -> dict[str, str] | None:
    """Per-test-case outcome from Surefire XML; ``None`` when no report exists."""
    reports = sorted((observation_dir / "execution_evidence" / "surefire").glob("*.xml"))
    if not reports:
        return None
    cases = {}
    for report in reports:
        for case in ElementTree.parse(report).getroot().iter("testcase"):
            name = f"{case.get('classname')}#{case.get('name')}"
            if case.find("failure") is not None:
                cases[name] = CASE_FAIL
            elif case.find("error") is not None:
                cases[name] = CASE_ERROR
            elif case.find("skipped") is not None:
                cases[name] = CASE_SKIPPED
            else:
                cases[name] = CASE_PASS
    return cases


def _read_diagnoses(batch_id: str, run_id: str) -> tuple[str, ...]:
    diagnoses_dir = TARGET.run_diagnoses_dir(batch_id, run_id)
    return tuple(
        str(read_json_object(path)["classification"])
        for path in sorted(diagnoses_dir.glob("attempt-*/diagnosis.json"))
    )


def _stage_attempts(run_root: Path, stage: str) -> Iterator[tuple[dict, dict]]:
    attempt_dirs = (run_root / "stages" / stage / "attempts").glob("attempt-*")
    for attempt_dir in sorted(attempt_dirs, key=lambda path: _number_suffix(path.name)):
        result_path = attempt_dir / "result.json"
        if not result_path.is_file():
            continue
        evidence_path = attempt_dir / "evidence.json"
        evidence = read_json_object(evidence_path) if evidence_path.is_file() else {}
        yield read_json_object(result_path), evidence


def _record_iteration(stage_result: Mapping, artifact_key: str) -> int:
    record = stage_result.get("artifacts", {}).get(artifact_key)
    match = re.search(r"iteration-(\d+)", record or "")
    if match is None:
        raise EvaluationInputError(f"{stage_result.get('stage')} attempt has no {artifact_key}")
    return int(match.group(1))


def _path_in_run(run_root: Path, run_id: str, recorded: str) -> Path:
    """Resolve a path recorded by the stage service, whatever its mount prefix."""
    marker = f"/{run_id}/"
    if marker not in recorded:
        raise EvaluationInputError(f"recorded path {recorded} is outside the run")
    return run_root / recorded.split(marker, 1)[1]


def _number_suffix(name: str) -> int:
    match = re.search(r"(\d+)$", name)
    if match is None:
        raise EvaluationInputError(f"{name} has no numeric suffix")
    return int(match.group(1))

@dataclass(frozen=True)
class Scope:
    """Where a row belongs; ``rq4_note`` qualifies the mutation population."""

    scope_type: str
    name: str
    language: str
    rq4_note: str = ""


class RowSink:
    """Collect output rows for one scope with uniform formatting."""

    def __init__(self, scope: Scope) -> None:
        self.scope = scope
        self.rows: list[dict[str, object]] = []

    def fraction(self, rq: str, metric: str, role: str, numerator: int, denominator: int,
                 category: str = "", note: str = "") -> None:
        value = numerator / denominator if denominator else None
        self._add(rq, metric, role, category, numerator, denominator, value, note)

    def mean(self, rq: str, metric: str, role: str, values: Sequence[float], note: str = "") -> None:
        self._add(rq, metric, role, "", "", len(values), mean(values) if values else None, note)

    def delta(self, rq: str, metric: str, role: str, before: float | None, after: float | None,
              denominator: int, note: str = "") -> None:
        value = after - before if before is not None and after is not None else None
        self._add(rq, metric, role, "", "", denominator, value, note)

    def distribution(self, rq: str, metric: str, role: str, counts: Counter, denominator: int) -> None:
        for category in sorted(counts, key=str):
            self.fraction(rq, metric, role, counts[category], denominator, category=str(category))

    def missing(self, rq: str, metric: str, role: str, note: str) -> None:
        """Record a metric that cannot be calculated, instead of omitting it."""
        self._add(rq, metric, role, "", "", "", None, note)

    def _add(self, rq, metric, role, category, numerator, denominator, value, note) -> None:
        scope_note = self.scope.rq4_note if rq == "RQ4" else ""
        notes = "; ".join(part for part in (scope_note, note) if part)
        self.rows.append(
            {
                "rq": rq,
                "metric": metric,
                "role": role,
                "scope_type": self.scope.scope_type,
                "scope": self.scope.name,
                "language": self.scope.language,
                "category": category,
                "numerator": numerator,
                "denominator": denominator,
                "value": "" if value is None else round(value, 6),
                "note": notes,
            }
        )


EXECUTABLE_SUITE_STATES = (SUITE_VALID, SUITE_REFERENCE_INVALID)


def trajectory_rows(sink: RowSink, rq: str, outcome: str, refinements_to_success: Sequence[int | None],
                    budget: int) -> None:
    """Cumulative and per-step success over the refinement number ``k``.

    ``refinements_to_success`` holds, per run of the population, the number of
    refinements after which it first succeeded, or ``None`` when it never did.
    """
    population = len(refinements_to_success)
    for k in range(budget + 1):
        within = sum(count is not None and count <= k for count in refinements_to_success)
        gained = sum(count == k for count in refinements_to_success)
        sink.fraction(rq, f"{outcome}_within_k", "descriptive", within, population, category=str(k))
        sink.fraction(rq, f"{outcome}_gain_at_k", "descriptive", gained, population, category=str(k))
    needed = [float(count) for count in refinements_to_success if count]
    sink.mean(rq, f"mean_refinements_to_{outcome}", "descriptive", needed,
              note="over runs that needed at least one refinement and succeeded")


def rq1_rows(sink: RowSink, runs: Sequence[RunFacts]) -> None:
    for snapshot, position, voy_role in (("final", -1, "primary"), ("initial", 0, "secondary")):
        endpoints = [run.suites[position] for run in runs if run.suites]
        executable = [suite for suite in endpoints if suite.state in EXECUTABLE_SUITE_STATES]
        valid = sum(suite.state == SUITE_VALID for suite in executable)
        sink.fraction("RQ1", f"{snapshot}_voy", voy_role, valid, len(runs))
        sink.fraction("RQ1", f"executability_rate_{snapshot}", "secondary", len(executable), len(runs))
        sink.fraction("RQ1", f"reference_pass_rate_{snapshot}", "secondary", valid, len(executable))

    suites = [suite for run in runs for suite in run.suites]
    executable = [suite for suite in suites if suite.state in EXECUTABLE_SUITE_STATES]
    sink.fraction("RQ1", "executability_rate_all_attempts", "descriptive", len(executable), len(suites))
    sink.fraction("RQ1", "reference_pass_rate_all_attempts", "descriptive",
                  sum(suite.state == SUITE_VALID for suite in executable), len(executable))
    trajectory_rows(
        sink, "RQ1", "valid_suite",
        [next((suite.iteration for suite in run.suites if suite.state == SUITE_VALID), None) for run in runs],
        max((run.test_refinement_budget for run in runs), default=0),
    )
    recovering = [run for run in runs if len(run.suites) > 1 and run.suites[0].state != SUITE_VALID]
    sink.fraction("RQ1", "test_refinement_recovery_rate", "descriptive",
                  sum(run.suites[-1].state == SUITE_VALID for run in recovering), len(recovering))
    reasons = Counter(
        suite.state if not suite.failure_stage else f"{suite.state}:{suite.failure_stage}"
        for suite in suites
        if suite.state != SUITE_VALID
    )
    sink.distribution("RQ1", "suite_failure_reason", "descriptive", reasons, len(suites))


def comparable_problem_languages(runs: Iterable[RunFacts]) -> frozenset[str]:
    """Languages whose parser reports a count everywhere and zero on parsed files."""
    seen, broken = set(), set()
    for run in runs:
        for verdict in run.syntax:
            seen.add(run.language)
            if verdict.problem_count is None or (verdict.is_parsed and verdict.problem_count != 0):
                broken.add(run.language)
    return frozenset(seen - broken)


def _syntax_refinements_to_parse(run: RunFacts) -> int | None:
    """Syntax refinements until T0 or a syntax-phase iteration parsed, else ``None``.

    The syntax phase ends at the first semantic refinement: a semantic
    refinement starts from a parsed transformation, so whatever it does to
    syntax is not parser feedback's doing.
    """
    semantic_starts = [
        r.iteration for r in run.refinements
        if r.artifact_type == TRANSFORMATION and r.purpose != SYNTAX_REFINEMENT
    ]
    phase_end = min(semantic_starts, default=None)
    for verdict in run.syntax:
        if phase_end is not None and verdict.iteration >= phase_end:
            break
        if verdict.is_parsed:
            return sum(
                r.purpose == SYNTAX_REFINEMENT and r.iteration <= verdict.iteration
                for r in run.refinements
            )
    return None


def rq2_rows(sink: RowSink, runs: Sequence[RunFacts], problem_languages: frozenset[str]) -> None:
    checked = [run for run in runs if run.syntax and run.syntax[0].iteration == 0]
    initial_parsed = sum(run.syntax[0].is_parsed for run in checked)
    refinements_to_parse = [_syntax_refinements_to_parse(run) for run in checked]
    post_syntax_parsed = sum(count is not None for count in refinements_to_parse)
    sink.fraction("RQ2", "ssr_initial", "secondary", initial_parsed, len(checked))
    sink.fraction("RQ2", "ssr_post_syntax", "secondary", post_syntax_parsed, len(checked))
    sink.delta("RQ2", "delta_ssr", "primary",
               initial_parsed / len(checked) if checked else None,
               post_syntax_parsed / len(checked) if checked else None, len(checked))
    sink.fraction("RQ2", "ssr_final", "descriptive", sum(run.syntax[-1].is_parsed for run in checked), len(checked))
    trajectory_rows(sink, "RQ2", "parsed", refinements_to_parse,
                    max((run.transformation_refinement_budget for run in checked), default=0))

    repair_population = [
        run for run in checked
        if not run.syntax[0].is_parsed and any(r.purpose == SYNTAX_REFINEMENT for r in run.refinements)
    ]
    repaired = problems_before = problems_after = 0
    for run in repair_population:
        first_parsed = next((v for v in run.syntax if v.iteration > 0 and v.is_parsed), None)
        repaired += first_parsed is not None
        if run.language in problem_languages:
            after = first_parsed or run.syntax[-1]
            problems_before += run.syntax[0].problem_count
            problems_after += after.problem_count
    sink.fraction("RQ2", "parser_repair_success_rate", "secondary", repaired, len(repair_population))

    languages = {run.language for run in runs}
    included = sorted(languages & problem_languages)
    excluded = sorted(languages - problem_languages)
    note = f"problem counts not comparable for: {', '.join(excluded)}" if excluded else ""
    if included:
        sink.fraction("RQ2", "parser_problem_reduction", "descriptive",
                      problems_before - problems_after, problems_before, note=note)
    else:
        sink.missing("RQ2", "parser_problem_reduction", "descriptive", note)

    syntax_refinements = [r for run in runs for r in run.refinements if r.purpose == SYNTAX_REFINEMENT]
    sink.fraction("RQ2", "noop_refinement_rate", "descriptive",
                  sum(r.is_noop for r in syntax_refinements), len(syntax_refinements))


def _final_passes(run: RunFacts) -> bool:
    last = run.executions[-1]
    return last.is_passed and last.transformation_iteration == run.final_transformation_iteration


def _pass_share(cases: Mapping[str, str]) -> float | None:
    judged = [outcome for outcome in cases.values() if outcome != CASE_SKIPPED]
    return sum(outcome == CASE_PASS for outcome in judged) / len(judged) if judged else None


def _same_suite_endpoints(run: RunFacts) -> tuple[Execution, Execution] | None:
    """T0 and Tfinal executions when both used one suite and have Surefire data."""
    first, last = run.executions[0], run.executions[-1]
    if (len(run.executions) < 2 or first.suite_iteration != last.suite_iteration
            or last.transformation_iteration != run.final_transformation_iteration
            or not first.test_cases or not last.test_cases):
        return None
    return first, last


def _first_candidate_executed(run: RunFacts) -> bool:
    return bool(run.executions) and run.executions[0].transformation_iteration == 0


def rq3_rows(sink: RowSink, runs: Sequence[RunFacts]) -> None:
    initially_parsed = [run for run in runs if run.syntax and run.syntax[0].iteration == 0 and run.syntax[0].is_parsed]
    unexecuted = sum(not _first_candidate_executed(run) for run in initially_parsed)
    sink.fraction("RQ3", "pass_at_1", "secondary",
                  sum(_first_candidate_executed(run) and run.executions[0].is_passed for run in initially_parsed),
                  len(initially_parsed),
                  note=f"{unexecuted} initially parsed runs lack a semantic execution of T0")

    executed = [run for run in runs if run.executions]
    sink.fraction("RQ3", "full_suite_success_before", "secondary",
                  sum(run.executions[0].is_passed for run in executed), len(executed))
    sink.fraction("RQ3", "full_suite_success_after", "secondary",
                  sum(_final_passes(run) for run in executed), len(executed))

    repair_population = [
        run for run in executed
        if not run.executions[0].is_passed
        and any(r.artifact_type == TRANSFORMATION and r.purpose == SEMANTIC_REFINEMENT for r in run.refinements)
    ]
    sink.fraction("RQ3", "semantic_repair_success_rate", "primary",
                  sum(_final_passes(run) for run in repair_population), len(repair_population))

    before_shares, after_shares = [], []
    for run in repair_population:
        endpoints = _same_suite_endpoints(run)
        if endpoints is None:
            continue
        before, after = (_pass_share(execution.test_cases) for execution in endpoints)
        if before is not None and after is not None:
            before_shares.append(before)
            after_shares.append(after)
    stpr_note = f"{len(repair_population) - len(before_shares)} repair runs lack same-suite per-test data"
    sink.mean("RQ3", "stpr_before", "primary", before_shares, note=stpr_note)
    sink.mean("RQ3", "stpr_after", "primary", after_shares, note=stpr_note)
    sink.delta("RQ3", "delta_stpr", "primary",
               mean(before_shares) if before_shares else None,
               mean(after_shares) if after_shares else None, len(before_shares), note=stpr_note)

    passing_at_t0 = regressed = 0
    for run in executed:
        endpoints = _same_suite_endpoints(run)
        if endpoints is None:
            continue
        before, after = endpoints
        for case, outcome in before.test_cases.items():
            if outcome == CASE_PASS and case in after.test_cases:
                passing_at_t0 += 1
                regressed += after.test_cases[case] in (CASE_FAIL, CASE_ERROR)
    sink.fraction("RQ3", "regression_rate", "secondary", regressed, passing_at_t0)

    diagnoses = Counter(classification for run in runs for classification in run.diagnoses)
    sink.distribution("RQ3", "diagnosis_outcome", "descriptive", diagnoses, sum(diagnoses.values()))

    for artifact_type in (TRANSFORMATION, SEMANTIC_TEST):
        routed = executed_routed = passed = 0
        for run in runs:
            key = "transformation_iteration" if artifact_type == TRANSFORMATION else "suite_iteration"
            for refinement in run.refinements:
                if refinement.artifact_type != artifact_type or refinement.purpose != SEMANTIC_REFINEMENT:
                    continue
                routed += 1
                following = next(
                    (e for e in run.executions
                     if e.attempt > (refinement.source_execution_attempt or 0)
                     and getattr(e, key) == refinement.iteration),
                    None,
                )
                if following is not None:
                    executed_routed += 1
                    passed += following.is_passed
        sink.fraction("RQ3", "diagnosis_gated_repair_success", "descriptive",
                      passed, executed_routed, category=artifact_type)
        sink.fraction("RQ3", "gated_refinement_never_executed", "descriptive",
                      routed - executed_routed, routed, category=artifact_type)

    trajectory_rows(sink, "RQ3", "semantic_pass",
                    [_semantic_refinements_to_pass(run) for run in repair_population],
                    max((run.transformation_refinement_budget for run in repair_population), default=0))


def _semantic_refinements_to_pass(run: RunFacts) -> int | None:
    """Transformation semantic refinements until the run's passing Tfinal, else ``None``."""
    first_pass = next((e for e in run.executions if e.is_passed), None)
    if first_pass is None or not _final_passes(run):
        return None
    return sum(
        r.artifact_type == TRANSFORMATION and r.purpose == SEMANTIC_REFINEMENT
        and r.iteration <= first_pass.transformation_iteration
        for r in run.refinements
    )


def rq4_rows(sink: RowSink, runs: Sequence[RunFacts]) -> None:
    with_data = [run for run in runs if run.mutant_row is not None]
    if not with_data:
        sink.missing("RQ4", "emkr", "primary", "no mutation results")
        return
    judged = [run for run in with_data if run.mutant_row["reference_result"] == REFERENCE_PASS]
    states: Counter = Counter()
    by_operator: dict[str, Counter] = {}
    for run in judged:
        for column, state in run.mutant_row.items():
            if not OPERATOR_COLUMN.fullmatch(column) or state == NOT_APPLICABLE:
                continue
            states[state] += 1
            by_operator.setdefault(column, Counter())[state] += 1
    applicable = sum(states.values())
    executable = states[KILLED] + states[SURVIVED]
    sink.fraction("RQ4", "emkr", "primary", states[KILLED], executable)
    sink.fraction("RQ4", "mutant_executability_rate", "secondary", executable, applicable)
    sink.fraction("RQ4", "applicable_mutant_kill_rate", "descriptive", states[KILLED], applicable)
    for operator in sorted(by_operator, key=_number_suffix):
        counts = by_operator[operator]
        sink.fraction("RQ4", "operator_emkr", "descriptive",
                      counts[KILLED], counts[KILLED] + counts[SURVIVED], category=operator)
    exclusions = Counter({state: n for state, n in states.items() if state not in (KILLED, SURVIVED)})
    sink.distribution("RQ4", "mutant_exclusion_reason", "descriptive", exclusions, applicable)
    not_judged = Counter(
        run.mutant_row["reference_result"] or "NO_RESULT" for run in with_data if run not in judged
    )
    sink.distribution("RQ4", "run_not_judged", "descriptive", not_judged, len(with_data))


def scope_rows(scope_type: str, name: str, runs: Sequence[RunFacts], problem_languages: frozenset[str],
               rq4_note: str = "") -> list[dict[str, object]]:
    """All metric rows of one scope: every language together, then each language."""
    rows = []
    languages = [ALL_LANGUAGES] + sorted({run.language for run in runs})
    for language in languages:
        selected = [run for run in runs if language == ALL_LANGUAGES or run.language == language]
        sink = RowSink(Scope(scope_type, name, language, rq4_note))
        rq1_rows(sink, selected)
        rq2_rows(sink, selected, problem_languages)
        rq3_rows(sink, selected)
        rq4_rows(sink, selected)
        rows.extend(sink.rows)
    return rows


def compute_rows(groups: Sequence[EvaluationGroup]) -> list[dict[str, object]]:
    facts_by_group = {
        group.name: [read_run_facts(group, batch_id, run_id) for batch_id, run_id in group.runs]
        for group in groups
    }
    problem_languages = comparable_problem_languages(
        run for runs in facts_by_group.values() for run in runs
    )
    rows = []
    for group in groups:
        rows.extend(scope_rows("group", group.name, facts_by_group[group.name], problem_languages))
    models = sorted({group.model for group in groups})
    for model in models:
        model_groups = [group for group in groups if group.model == model]
        if len(model_groups) < 2:
            continue
        missing = [group.name for group in model_groups if group.mutant_rows is None]
        note = f"excludes groups without mutation results: {', '.join(missing)}" if missing else ""
        runs = [run for group in model_groups for run in facts_by_group[group.name]]
        rows.extend(scope_rows("model", model, runs, problem_languages, note))
    missing = [group.name for group in groups if group.mutant_rows is None]
    note = f"excludes groups without mutation results: {', '.join(missing)}" if missing else ""
    every_run = [run for group in groups for run in facts_by_group[group.name]]
    rows.extend(scope_rows("all", ALL_GROUPS, every_run, problem_languages, note))
    return rows

def write_rows(path: Path, rows: Sequence[Mapping[str, object]], decimal_comma: bool) -> None:
    """Write the rows atomically; ``decimal_comma`` targets comma-decimal spreadsheets."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, delimiter=";" if decimal_comma else ",")
        writer.writeheader()
        for row in rows:
            if decimal_comma and isinstance(row["value"], float):
                row = {**row, "value": str(row["value"]).replace(".", ",")}
            writer.writerow(row)
    temporary.replace(path)


def print_primary_summary(rows: Sequence[Mapping[str, object]]) -> None:
    """Print the primary metrics of every scope over all languages."""
    print(f"{'scope':34} {'metric':30} {'value':>9}  n/d")
    for row in rows:
        if row["role"] != "primary" or row["language"] != ALL_LANGUAGES:
            continue
        value = row["value"]
        shown = f"{value:9.3f}" if isinstance(value, float) else f"{'—':>9}"
        print(f"{str(row['scope']):34} {str(row['metric']):30} {shown}  {row['numerator']}/{row['denominator']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--selection-root", type=Path, default=DEFAULT_SELECTION_ROOT,
                        help="tree of evaluation groups (default: artifacts/Chosen_for_evaluation)")
    parser.add_argument("--output", type=Path, required=True, help="CSV file to write")
    parser.add_argument("--decimal-comma", action="store_true",
                        help="write ';'-separated cells with a decimal comma for German/Russian spreadsheets")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rows = compute_rows(discover_groups(args.selection_root))
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    write_rows(args.output, rows, args.decimal_comma)
    print_primary_summary(rows)
    print(f"\nwrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
