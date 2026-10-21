"""Run-level failure analysis for the runs selected by ``rq_metrics``."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from evaluation._common import EvaluationInputError, read_csv, read_json_object
from evaluation.rq_metrics import (
    DEFAULT_SELECTION_ROOT,
    KILLED,
    NOT_APPLICABLE,
    OPERATOR_COLUMN,
    REFERENCE_PASS,
    SEMANTIC_REFINEMENT,
    SEMANTIC_TEST,
    SUITE_NO_VERDICT,
    SUITE_NOT_EXECUTABLE,
    SUITE_REFERENCE_INVALID,
    SUITE_VALID,
    SURVIVED,
    SYNTAX_REFINEMENT,
    TRANSFORMATION,
    CASE_ERROR,
    CASE_FAIL,
    CASE_PASS,
    EvaluationGroup,
    Execution,
    RunFacts,
    _final_passes,
    _path_in_run,
    _syntax_refinements_to_parse,
    discover_groups,
    read_run_facts,
)
from llm4mtl.paths import REPO_ROOT, TARGET


MUTANTS_MANIFEST = REPO_ROOT / "evaluation" / "mutants" / "manifest.json"
FINGERPRINT_LENGTH = 220
RATIONALE_LENGTH = 400

# Message classification
# Ordered: the first matching pattern names the class. Patterns are matched
# against "<failure_stage>: <error_summary>".
EXECUTION_FAILURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("TIMEOUT", re.compile(r"^timeout:|timed out", re.IGNORECASE)),
    ("ENVIRONMENT_GUI_INTERACTION", re.compile(r"X11 DISPLAY|HeadlessException")),
    ("REACTIONS_EMPTY_CHANGE", re.compile(r"Cannot identify the packages of this change")),
    ("MODEL_BINDING_MISMATCH", re.compile(
        r"Cannot find reference model|Could not find model|Type '\w+!\w+' not found")),
    ("TRANSFORMATION_COMPILE_ERROR", re.compile(
        r"^transformation_parse:|ATL parse errors|Compilation errors")),
    ("MODEL_NONCONFORMANT", re.compile(
        r"^model_loading:|Error whilst loading model|ClassNotFoundException|IllegalValueException"
        r"|Unresolved reference|XML version")),
    ("RUNTIME_UNDEFINED_NAVIGATION", re.compile(
        r"OclUndefined|undefined object|Property '\w+' not found|Cannot invoke|NullPointerException")),
    ("RUNTIME_OPERATION_NOT_FOUND", re.compile(
        r"Operation not found|Method '\w+' not found|Invalid number \(or types\) of arguments")),
    ("RUNTIME_UNRESOLVED_NAME_OR_TYPE", re.compile(
        r"Undefined variable, type or model|Feature \w+ does not exist|must be of type|Cannot iterate on")),
    ("ASSERTION_COUNT", re.compile(r"\bcount assertion for")),
    ("ASSERTION_FEATURE_VALUES", re.compile(r"\bfeatureValues assertion for")),
    ("ASSERTION_PATH_VALUES", re.compile(r"\bpathValues assertion for")),
    ("ASSERTION_OBJECTS", re.compile(r"\bobjects assertion for")),
    ("ASSERTION_OTHER", re.compile(r"^assertion_failure:")),
    ("ENGINE_CRASH", re.compile(r"StackOverflowError|several rules as default|^engine_runtime:")),
)

OTHER_EXECUTION_FAILURE = "OTHER_RUNTIME"


def classify_execution_failure(failure_stage: str, error_summary: str) -> str:
    """Name the failure class of one suite execution (reference or generated T)."""
    text = f"{failure_stage}: {error_summary}"
    for failure_class, pattern in EXECUTION_FAILURE_PATTERNS:
        if pattern.search(text):
            return failure_class
    return OTHER_EXECUTION_FAILURE


_HEX_IDENTITY = re.compile(r"@[0-9a-f]{5,}")
_RUNTIME_PATH = re.compile(r"(file:)?/app/\S+")
_TEST_PREFIX = re.compile(r"^[\w$]+(\(Path\))?: ")
_ASSERTION_TARGET = re.compile(r"(\w+ assertion for [\w:!.]+)")


def execution_fingerprint(error_summary: str) -> str:
    """A short, run-independent form of an execution failure message.

    Assertion failures keep only the assertion kind and the checked metaclass,
    so the same mismatch in different runs groups together. Other messages lose
    the failing test name, object identities and paths.
    """
    first_line = error_summary.strip().splitlines()[0] if error_summary.strip() else ""
    assertion = _ASSERTION_TARGET.search(first_line)
    if assertion:
        return assertion.group(1)
    message = _TEST_PREFIX.sub("", first_line)
    message = _HEX_IDENTITY.sub("", _RUNTIME_PATH.sub("<path>", message))
    return message[:FINGERPRINT_LENGTH]


_ATL_PROBLEM = re.compile(r"description: (.*?)\)(?:\s+- |\s*$)", re.DOTALL)
_ETL_PROBLEM = re.compile(r"ERROR (?:line \d+:\d+ |- )(.*?)(?=\s*ERROR (?:line|-)|$)", re.DOTALL)
_REACTIONS_ISSUES = re.compile(r"Syntax issues \(\d+\):\s*(.*)", re.DOTALL)
_INFERRER_CRASH = re.compile(r"Error calling inferrer (\S+: [^\t\n]*)")

PARSER_GRAMMAR = re.compile(
    r"mismatched input|missing '|missing EOF|no viable alternative|extraneous input|required \(\.\.\.\)\+ loop")
PARSER_LINKING = re.compile(
    r"cannot be resolved|is undefined|missing type|Type mismatch|cannot be inserted|cannot be contained"
    r"|must be initial")
PARSER_CRASH = re.compile(r"Exception|Error calling inferrer")

PARSER_CATEGORIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("KEYWORD_AS_IDENTIFIER", re.compile(r"mismatched input '\w+' expecting NAME|at character '\^'")),
    ("CONTROL_FLOW_SYNTAX", re.compile(r"'elseif'|'endif'|input 'then'|input 'else'")),
    ("RULE_DECLARATION_SYNTAX", re.compile(r"'extends'|'transform'")),
    ("STATIC_CHECK_ERROR", re.compile(r"InPatternElement with varName")),
)


@dataclass(frozen=True)
class ParserFailure:
    """The classified parser messages of one rejected transformation iteration."""

    category: str
    error_kinds: str
    fingerprint: str
    problem_messages: tuple[str, ...]


def parser_messages(diagnostics: str) -> tuple[str, ...]:
    """Split one parser diagnostics string into individual problem messages."""
    reactions = _REACTIONS_ISSUES.search(diagnostics)
    if reactions:
        parts = reactions.group(1).split("(ERROR)")
        return tuple(part.strip() for part in parts if part.strip())
    crash = _INFERRER_CRASH.search(diagnostics)
    if crash:
        return (crash.group(1).strip(),)
    for pattern in (_ATL_PROBLEM, _ETL_PROBLEM):
        found = [" ".join(match.split()) for match in pattern.findall(diagnostics)]
        if found:
            return tuple(found)
    stripped = " ".join(_RUNTIME_PATH.sub("<path>", diagnostics).split())
    return (stripped[:FINGERPRINT_LENGTH],) if stripped else ()


def classify_parser_messages(language: str, messages: Sequence[str]) -> ParserFailure:
    """Name the dominant cause of one parser rejection.

    A grammar error usually cascades into linking errors in the same file
    (Reactions reports both), so a grammar error names the category whenever
    one is present; linking alone is ``UNRESOLVED_REFERENCE``.
    """
    has_grammar = any(PARSER_GRAMMAR.search(message) for message in messages)
    has_linking = any(PARSER_LINKING.search(message) for message in messages)
    has_crash = any(PARSER_CRASH.search(message) for message in messages)
    kinds = "+".join(
        kind for kind, present in (("grammar", has_grammar), ("linking", has_linking), ("crash", has_crash))
        if present
    )
    # The first specific message names the category: a parser reports the root
    # cause first and the errors it provokes after it.
    category = next(
        (name for message in messages for name, pattern in PARSER_CATEGORIES if pattern.search(message)),
        "",
    )
    if not category:
        if has_crash and not has_grammar:
            category = "PARSER_CRASH"
        elif has_grammar:
            category = "REACTIONS_BLOCK_GRAMMAR" if language == "reactions" else "OTHER_GRAMMAR"
        elif has_linking:
            category = "UNRESOLVED_REFERENCE"
        else:
            category = "OTHER_PARSER_ERROR"
    distinct = list(dict.fromkeys(messages))
    return ParserFailure(category, kinds, " | ".join(distinct[:3])[:FINGERPRINT_LENGTH * 2], tuple(messages))



@dataclass(frozen=True)
class StageAttempt:
    stage: str
    attempt: int
    status: str
    outcome_code: str
    transformation_iteration: int | None
    suite_iteration: int | None
    detail: str
    failure_class: str
    recorded_at: str


@dataclass(frozen=True)
class DiagnosisRecord:
    number: int
    execution_attempt: int | None
    classification: str
    test_case: str
    rationale: str
    recorded_at: str


@dataclass(frozen=True)
class RunEvidence:
    """Messages and timestamps of one run, beside the facts ``rq_metrics`` reads."""

    batch_id: str
    task: str
    terminal_result: Mapping
    suite_observations: Mapping[int, Mapping]
    syntax_diagnostics: Mapping[int, str]
    execution_observations: Mapping[int, Mapping]
    stage_attempts: tuple[StageAttempt, ...]
    diagnoses: tuple[DiagnosisRecord, ...]
    refinement_times: Mapping[tuple[str, int], str]


SUITE_STAGES = ("extract", "technical-validation", "reference-validation")
STAGES = SUITE_STAGES + ("syntax-validation", "execution")
_ITERATION = re.compile(r"iteration-(\d+)")
_EXECUTION_ATTEMPT = re.compile(r"diagnosis/execution/attempt-(\d+)/")
_REPORT_CASE = re.compile(r"__[^_].*?_\d{3}__(.+?)__[\w-]+\.json$")


def read_run_evidence(batch_id: str, run_id: str) -> RunEvidence:
    run_root = TARGET.run_dir(batch_id, run_id)
    manifest = read_json_object(run_root / "manifest.json")
    task = str(manifest["task"])
    stage_times = _stage_finish_times(run_root / "events.jsonl")

    suite_observations = {}
    for path in run_root.glob(f"observations/{task}/*/*/*/suite_execution.json"):
        suite_observations[int(path.parent.name.rsplit("_", 1)[1])] = read_json_object(path)["observation"]

    syntax_diagnostics: dict[int, str] = {}
    execution_observations: dict[int, Mapping] = {}
    attempts = []
    for stage in STAGES:
        attempt_dirs = sorted((run_root / "stages" / stage / "attempts").glob("attempt-*"),
                              key=lambda path: int(path.name.rsplit("-", 1)[1]))
        for attempt_dir in attempt_dirs:
            if not (attempt_dir / "result.json").is_file():
                continue
            result = read_json_object(attempt_dir / "result.json")
            evidence_path = attempt_dir / "evidence.json"
            evidence = read_json_object(evidence_path) if evidence_path.is_file() else {}
            attempt = int(result.get("attempt", attempt_dir.name.rsplit("-", 1)[1]))
            transformation_iteration = _artifact_iteration(result, "transformation_generation_record")
            suite_iteration = _artifact_iteration(result, "semantic_test_generation_record")
            detail, failure_class = "", ""
            details = evidence.get("details", {})
            if stage == "syntax-validation":
                diagnostics = " || ".join(details.get("diagnostics", {}).values())
                if transformation_iteration is not None:
                    syntax_diagnostics[transformation_iteration] = diagnostics
                if result["status"] != "passed":
                    failure = classify_parser_messages(str(manifest["language"]), parser_messages(diagnostics))
                    failure_class, detail = failure.category, failure.fingerprint
            elif stage == "execution":
                pair = details["pairs"][0]
                observation = read_json_object(_path_in_run(run_root, run_id, pair["evidence"]))["observation"]
                execution_observations[attempt] = observation
                if not pair["assertions_passed"]:
                    detail = execution_fingerprint(observation.get("error_summary") or "")
                    failure_class = classify_execution_failure(
                        observation.get("failure_stage") or "", observation.get("error_summary") or "")
            elif stage in ("technical-validation", "reference-validation"):
                verdict = (details.get("verdicts") or [{}])[0]
                if verdict.get("error_summary"):
                    detail = execution_fingerprint(verdict["error_summary"])
                    failure_class = classify_execution_failure(
                        verdict.get("failure_stage") or "", verdict["error_summary"])
            attempts.append(
                StageAttempt(
                    stage=stage,
                    attempt=attempt,
                    status=str(result["status"]),
                    outcome_code=str(result.get("outcome_code") or ""),
                    transformation_iteration=transformation_iteration,
                    suite_iteration=suite_iteration,
                    detail=detail,
                    failure_class=failure_class,
                    recorded_at=stage_times.get((stage, attempt), ""),
                )
            )

    diagnoses = []
    for path in sorted(TARGET.run_diagnoses_dir(batch_id, run_id).glob("attempt-*/diagnosis.json")):
        record = read_json_object(path)
        evidence_ref = str(record.get("evidence_ref") or "")
        attempt_match = _EXECUTION_ATTEMPT.search(evidence_ref)
        case_match = _REPORT_CASE.search(evidence_ref)
        diagnoses.append(
            DiagnosisRecord(
                number=int(path.parent.name.rsplit("-", 1)[1]),
                execution_attempt=int(attempt_match.group(1)) if attempt_match else None,
                classification=str(record["classification"]),
                test_case=case_match.group(1) if case_match else "",
                rationale=" ".join(str(record.get("rationale") or "").split())[:RATIONALE_LENGTH],
                recorded_at=str(record.get("created_at") or ""),
            )
        )

    refinement_times = {}
    for artifact_type in (TRANSFORMATION, SEMANTIC_TEST):
        for path in (run_root / "generations" / artifact_type).glob("iteration-*/generation.json"):
            record = read_json_object(path)
            refinement_times[(artifact_type, int(record["iteration"]))] = str(record.get("recorded_at") or "")

    return RunEvidence(
        batch_id=batch_id,
        task=task,
        terminal_result=read_json_object(run_root / "result.json"),
        suite_observations=suite_observations,
        syntax_diagnostics=syntax_diagnostics,
        execution_observations=execution_observations,
        stage_attempts=tuple(attempts),
        diagnoses=tuple(diagnoses),
        refinement_times=refinement_times,
    )


def _stage_finish_times(events_path: Path) -> dict[tuple[str, int], str]:
    times = {}
    if not events_path.is_file():
        return times
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == "stage_finished" and event.get("attempt") is not None:
            times[(str(event["stage"]), int(event["attempt"]))] = str(event["ts"])
    return times


def _artifact_iteration(stage_result: Mapping, key: str) -> int | None:
    match = _ITERATION.search(stage_result.get("artifacts", {}).get(key) or "")
    return int(match.group(1)) if match else None


RQ3_NOT_EXECUTED = "NOT_EXECUTED"
RQ3_PASSED_INITIALLY = "PASSED_INITIALLY"
RQ3_RECOVERED = "RECOVERED"
RQ3_FAILED_NOT_REFINED = "FAILED_NOT_REFINED"
RQ3_FAILED_AFTER_REFINEMENT = "FAILED_AFTER_REFINEMENT"

TERMINAL_STOP_REASONS = {
    "AMBIGUOUS_SOURCE_DIAGNOSIS": "STOPPED_AMBIGUOUS_DIAGNOSIS",
    "NO_ELIGIBLE_SOURCE_DIAGNOSIS_REPORTS": "STOPPED_NO_ELIGIBLE_DIAGNOSIS",
}
TEST_REPAIR_TERMINALS = ("DIAGNOSED_TEST_DEFECT", "REFERENCE_VALIDATION_FAILED", "TEST_SPEC_INVALID")


def semantic_population(run: RunFacts) -> str:
    """Where the run sits in the RQ3 funnel 473 -> 164 -> 120 -> 93."""
    if not run.executions:
        return RQ3_NOT_EXECUTED
    if run.executions[0].is_passed:
        return RQ3_PASSED_INITIALLY
    entered = any(r.artifact_type == TRANSFORMATION and r.purpose == SEMANTIC_REFINEMENT for r in run.refinements)
    if _final_passes(run):
        return RQ3_RECOVERED
    return RQ3_FAILED_AFTER_REFINEMENT if entered else RQ3_FAILED_NOT_REFINED


def failing_cases(execution: Execution) -> frozenset[str] | None:
    if execution.test_cases is None:
        return None
    return frozenset(case for case, outcome in execution.test_cases.items() if outcome in (CASE_FAIL, CASE_ERROR))


def semantic_outcome_reason(run: RunFacts, terminal_state: str, fingerprints: Mapping[int, str]) -> str:
    """Why a semantically failing run ended without a passing Tfinal.

    ``fingerprints`` maps an execution attempt to its failure fingerprint; it
    decides "same failure" when no per-test Surefire data exists.
    """
    population = semantic_population(run)
    if population in (RQ3_NOT_EXECUTED, RQ3_PASSED_INITIALLY):
        return ""
    if population == RQ3_RECOVERED:
        entered = any(r.artifact_type == TRANSFORMATION and r.purpose == SEMANTIC_REFINEMENT
                      for r in run.refinements)
        return "RECOVERED_BY_TRANSFORMATION_REFINEMENT" if entered else "RECOVERED_WITHOUT_TRANSFORMATION_REFINEMENT"
    if run.executions[-1].transformation_iteration != run.final_transformation_iteration:
        return "REFINEMENT_BROKE_SYNTAX"
    if terminal_state in TERMINAL_STOP_REASONS:
        return TERMINAL_STOP_REASONS[terminal_state]
    if terminal_state.startswith(TEST_REPAIR_TERMINALS):
        return "ROUTED_TO_TEST_BUDGET_EXHAUSTED"
    if terminal_state.startswith("DIAGNOSED_TRANSFORMATION_DEFECT"):
        if population == RQ3_FAILED_NOT_REFINED:
            return "BUDGET_SPENT_ON_SYNTAX"
        first = next(e for e in run.executions if not e.is_passed)
        last = run.executions[-1]
        first_cases, last_cases = failing_cases(first), failing_cases(last)
        if first.suite_iteration == last.suite_iteration and first_cases is not None and last_cases is not None:
            is_same = first_cases == last_cases
        else:
            is_same = fingerprints.get(first.attempt) == fingerprints.get(last.attempt)
        return "BUDGET_EXHAUSTED_SAME_FAILURE" if is_same else "BUDGET_EXHAUSTED_DIFFERENT_FAILURE"
    return f"OTHER:{terminal_state}"


def regressed_cases(run: RunFacts) -> int | None:
    """Test cases PASS at T0 and FAIL/ERROR at Tfinal under the same suite."""
    if len(run.executions) < 2:
        return None
    first, last = run.executions[0], run.executions[-1]
    if (first.suite_iteration != last.suite_iteration or not first.test_cases or not last.test_cases
            or last.transformation_iteration != run.final_transformation_iteration):
        return None
    return sum(
        outcome == CASE_PASS and last.test_cases.get(case) in (CASE_FAIL, CASE_ERROR)
        for case, outcome in first.test_cases.items()
    )



RUN_FIELDS = (
    "batch_id", "run_id", "group", "model", "transformation_model", "strategy", "language", "task",
    "terminal_state",
    # RQ1
    "test_suite_iterations", "test_initial_state", "test_initial_executable", "test_initial_reference_pass",
    "test_final_state", "test_final_executable", "test_final_reference_pass", "test_failure_reason",
    "test_failure_stage", "test_failure_class", "test_failure_fingerprint",
    # RQ2
    "syntax_checked", "syntax_initial_pass", "syntax_post_pass", "syntax_final_pass", "syntax_refinement_count",
    "parser_initial_category", "parser_initial_fingerprint",
    "parser_failure_category", "parser_failure_error_kinds", "parser_failure_fingerprint",
    # RQ3
    "semantic_population", "semantic_initial_full_pass", "entered_semantic_refinement", "diagnosis_records",
    "diagnosis_transformation_defect", "diagnosis_test_defect", "diagnosis_ambiguous", "diagnosis_outcome",
    "routed_artifacts", "semantic_refinement_count", "test_semantic_refinement_count",
    "transformation_refinement_budget", "semantic_executions", "semantic_final_full_pass",
    "semantic_outcome_reason", "semantic_initial_failure_class", "semantic_initial_fingerprint",
    "semantic_final_failure_class", "semantic_failure_fingerprint", "initial_failing_cases",
    "final_failing_cases", "regressed_cases",
    # RQ4
    "mutant_reference_result", "mutants_applicable", "mutants_killed", "mutants_survived",
    "mutants_parse_failed", "mutants_error", "mutants_not_judged", "survived_operators", "error_operators",
)


def _flag(value: bool | None) -> str:
    return "" if value is None else ("true" if value else "false")


def _suite_executable(state: str) -> bool | None:
    if state == SUITE_NO_VERDICT:
        return False
    return state in (SUITE_VALID, SUITE_REFERENCE_INVALID)


def _suite_reference_pass(state: str) -> bool | None:
    return None if state in (SUITE_NOT_EXECUTABLE, SUITE_NO_VERDICT) else state == SUITE_VALID


def _test_failure_reason(state: str) -> str:
    return {
        SUITE_NOT_EXECUTABLE: "NON_EXECUTABLE",
        SUITE_REFERENCE_INVALID: "EXECUTABLE_REFERENCE_INCONSISTENT",
        SUITE_NO_VERDICT: "NO_VERDICT",
    }.get(state, "")


def run_row(run: RunFacts, evidence: RunEvidence, metadata: Mapping[str, str],
            mutant_columns: Sequence[str]) -> dict[str, object]:
    terminal_state = str(evidence.terminal_result.get("terminal_state") or "")
    row: dict[str, object] = {
        "batch_id": evidence.batch_id,
        "run_id": run.run_id,
        "group": run.group,
        "model": run.model,
        "transformation_model": metadata.get("transformation_model", ""),
        "strategy": metadata.get("transformation_strategy", ""),
        "language": run.language,
        "task": evidence.task,
        "terminal_state": terminal_state,
    }
    row.update(_rq1_columns(run, evidence))
    row.update(_rq2_columns(run, evidence))
    row.update(_rq3_columns(run, evidence, terminal_state))
    row.update(_rq4_columns(run, mutant_columns))
    return row


def _rq1_columns(run: RunFacts, evidence: RunEvidence) -> dict[str, object]:
    if not run.suites:
        return {"test_suite_iterations": 0, "test_final_state": "NO_SUITE", "test_failure_reason": "NO_SUITE"}
    first, last = run.suites[0], run.suites[-1]
    columns: dict[str, object] = {
        "test_suite_iterations": len(run.suites),
        "test_initial_state": first.state,
        "test_initial_executable": _flag(_suite_executable(first.state)),
        "test_initial_reference_pass": _flag(_suite_reference_pass(first.state)),
        "test_final_state": last.state,
        "test_final_executable": _flag(_suite_executable(last.state)),
        "test_final_reference_pass": _flag(_suite_reference_pass(last.state)),
        "test_failure_reason": _test_failure_reason(last.state),
    }
    if last.state == SUITE_VALID:
        return columns
    observation = evidence.suite_observations.get(last.iteration)
    if observation is not None:
        summary = observation.get("error_summary") or ""
        columns["test_failure_stage"] = observation.get("failure_stage") or ""
        columns["test_failure_class"] = classify_execution_failure(columns["test_failure_stage"], summary)
        columns["test_failure_fingerprint"] = execution_fingerprint(summary)
    else:
        failed_suite_stages = [a for a in evidence.stage_attempts if a.stage in SUITE_STAGES and a.status != "passed"]
        last_suite_stage = max(failed_suite_stages, key=lambda a: a.recorded_at, default=None)
        columns["test_failure_class"] = last_suite_stage.outcome_code if last_suite_stage else "NO_SUITE_STAGE"
    return columns


def _rq2_columns(run: RunFacts, evidence: RunEvidence) -> dict[str, object]:
    is_checked = bool(run.syntax) and run.syntax[0].iteration == 0
    if not is_checked:
        return {"syntax_checked": "false"}
    refinements_to_parse = _syntax_refinements_to_parse(run)
    columns: dict[str, object] = {
        "syntax_checked": "true",
        "syntax_initial_pass": _flag(run.syntax[0].is_parsed),
        "syntax_post_pass": _flag(refinements_to_parse is not None),
        "syntax_final_pass": _flag(run.syntax[-1].is_parsed),
        "syntax_refinement_count": sum(r.purpose == SYNTAX_REFINEMENT for r in run.refinements),
    }
    if not run.syntax[0].is_parsed:
        initial = classify_parser_messages(run.language, parser_messages(evidence.syntax_diagnostics.get(0, "")))
        columns["parser_initial_category"] = initial.category
        columns["parser_initial_fingerprint"] = initial.fingerprint
    if refinements_to_parse is None:
        last_failed = [v for v in run.syntax if not v.is_parsed][-1]
        final = classify_parser_messages(
            run.language, parser_messages(evidence.syntax_diagnostics.get(last_failed.iteration, "")))
        columns["parser_failure_category"] = final.category
        columns["parser_failure_error_kinds"] = final.error_kinds
        columns["parser_failure_fingerprint"] = final.fingerprint
    return columns


def _execution_failure(evidence: RunEvidence, attempt: int) -> tuple[str, str]:
    observation = evidence.execution_observations.get(attempt, {})
    summary = observation.get("error_summary") or ""
    return (classify_execution_failure(observation.get("failure_stage") or "", summary),
            execution_fingerprint(summary))


def routed_artifacts(run: RunFacts) -> str:
    routed = sorted({r.artifact_type for r in run.refinements if r.purpose == SEMANTIC_REFINEMENT})
    return "+".join(routed) if routed else "none"


def diagnosis_outcome(classifications: Iterable[str]) -> str:
    """The distinct verdicts of a run, most frequent first (ties alphabetical)."""
    counts = Counter(classifications)
    return "+".join(sorted(counts, key=lambda name: (-counts[name], name)))


def _rq3_columns(run: RunFacts, evidence: RunEvidence, terminal_state: str) -> dict[str, object]:
    population = semantic_population(run)
    diagnoses = Counter(record.classification for record in evidence.diagnoses)
    columns: dict[str, object] = {
        "semantic_population": population,
        "diagnosis_records": sum(diagnoses.values()),
        "diagnosis_transformation_defect": diagnoses["TRANSFORMATION_DEFECT"],
        "diagnosis_test_defect": diagnoses["TEST_DEFECT"],
        "diagnosis_ambiguous": diagnoses["AMBIGUOUS"],
        "diagnosis_outcome": diagnosis_outcome(record.classification for record in evidence.diagnoses),
        "routed_artifacts": routed_artifacts(run),
        "semantic_refinement_count": sum(
            r.artifact_type == TRANSFORMATION and r.purpose == SEMANTIC_REFINEMENT for r in run.refinements),
        "test_semantic_refinement_count": sum(
            r.artifact_type == SEMANTIC_TEST and r.purpose == SEMANTIC_REFINEMENT for r in run.refinements),
        "transformation_refinement_budget": run.transformation_refinement_budget,
        "semantic_executions": len(run.executions),
    }
    if population == RQ3_NOT_EXECUTED:
        return columns
    fingerprints = {e.attempt: _execution_failure(evidence, e.attempt)[1] for e in run.executions}
    first, last = run.executions[0], run.executions[-1]
    columns.update({
        "semantic_initial_full_pass": _flag(first.is_passed),
        "entered_semantic_refinement": _flag(not first.is_passed and columns["semantic_refinement_count"] > 0),
        "semantic_final_full_pass": _flag(_final_passes(run)),
        "semantic_outcome_reason": semantic_outcome_reason(run, terminal_state, fingerprints),
    })
    if not first.is_passed:
        columns["semantic_initial_failure_class"], columns["semantic_initial_fingerprint"] = (
            _execution_failure(evidence, first.attempt))
        cases = failing_cases(first)
        columns["initial_failing_cases"] = "" if cases is None else len(cases)
    if not last.is_passed:
        columns["semantic_final_failure_class"], columns["semantic_failure_fingerprint"] = (
            _execution_failure(evidence, last.attempt))
        cases = failing_cases(last)
        columns["final_failing_cases"] = "" if cases is None else len(cases)
    regressed = regressed_cases(run)
    columns["regressed_cases"] = "" if regressed is None else regressed
    return columns


def _rq4_columns(run: RunFacts, mutant_columns: Sequence[str]) -> dict[str, object]:
    row = run.mutant_row
    if row is None:
        return {}
    cells = {column: row[column] for column in mutant_columns if row.get(column, NOT_APPLICABLE) != NOT_APPLICABLE}
    states = Counter(cells.values())
    return {
        "mutant_reference_result": row["reference_result"],
        "mutants_applicable": len(cells),
        "mutants_killed": states[KILLED],
        "mutants_survived": states[SURVIVED],
        "mutants_parse_failed": states["PARSE_FAILED"],
        "mutants_error": states["ERROR"],
        "mutants_not_judged": states["NOT_JUDGED"],
        "survived_operators": " ".join(op for op, state in cells.items() if state == SURVIVED),
        "error_operators": " ".join(op for op, state in cells.items() if state == "ERROR"),
    }


EVENT_FIELDS = (
    "batch_id", "run_id", "group", "language", "task", "sequence", "recorded_at", "kind", "attempt",
    "transformation_iteration", "suite_iteration", "execution_attempt", "artifact_type", "purpose",
    "outcome", "failure_class", "detail",
)


def event_rows(run: RunFacts, evidence: RunEvidence) -> list[dict[str, object]]:
    """Stage attempts, diagnosis records and refinements of one run, in recorded order."""
    base = {"batch_id": evidence.batch_id, "run_id": run.run_id, "group": run.group,
            "language": run.language, "task": evidence.task}
    events: list[dict[str, object]] = []
    for attempt in evidence.stage_attempts:
        events.append({
            **base, "recorded_at": attempt.recorded_at, "kind": attempt.stage, "attempt": attempt.attempt,
            "transformation_iteration": attempt.transformation_iteration,
            "suite_iteration": attempt.suite_iteration, "outcome": attempt.outcome_code,
            "failure_class": attempt.failure_class,
            "detail": attempt.detail[:FINGERPRINT_LENGTH * 2].replace("\n", " "),
        })
    for record in evidence.diagnoses:
        events.append({
            **base, "recorded_at": record.recorded_at, "kind": "diagnosis", "attempt": record.number,
            "execution_attempt": record.execution_attempt, "outcome": record.classification,
            "detail": f"{record.test_case}: {record.rationale}" if record.test_case else record.rationale,
        })
    for refinement in run.refinements:
        events.append({
            **base,
            "recorded_at": evidence.refinement_times.get((refinement.artifact_type, refinement.iteration), ""),
            "kind": "refinement", "attempt": refinement.iteration,
            "transformation_iteration": refinement.iteration if refinement.artifact_type == TRANSFORMATION else "",
            "suite_iteration": refinement.iteration if refinement.artifact_type == SEMANTIC_TEST else "",
            "execution_attempt": refinement.source_execution_attempt, "artifact_type": refinement.artifact_type,
            "purpose": refinement.purpose, "outcome": "NOOP" if refinement.is_noop else "CHANGED",
        })
    events.sort(key=lambda event: (str(event["recorded_at"]), str(event["kind"])))
    for sequence, event in enumerate(events, start=1):
        event["sequence"] = sequence
    return events


MUTANT_FIELDS = (
    "language", "task", "operator", "category", "judged_runs", "killed", "survived", "parse_failed", "error",
    "emkr", "changed_construct", "original", "mutated",
)


def mutant_rows(runs: Sequence[RunFacts], tasks: Mapping[str, str],
                manifest: Mapping) -> list[dict[str, object]]:
    """Per applicable mutant: its states over the runs whose final suite passed the reference."""
    states: dict[tuple[str, str, str], Counter] = {}
    for run in runs:
        row = run.mutant_row
        if row is None or row["reference_result"] != REFERENCE_PASS:
            continue
        for column, state in row.items():
            if OPERATOR_COLUMN.fullmatch(column) and state != NOT_APPLICABLE:
                states.setdefault((run.language, tasks[run.run_id], column), Counter())[state] += 1
    entries = {(m["language"].lower(), m["task"], m["mutant"]): m for m in manifest["mutants"]}
    rows = []
    for key in sorted(states, key=lambda k: (k[0], k[1], int(k[2].lstrip("M")))):
        counts, entry = states[key], entries.get(key, {})
        executable = counts[KILLED] + counts[SURVIVED]
        rows.append({
            "language": key[0], "task": key[1], "operator": key[2], "category": entry.get("category", ""),
            "judged_runs": sum(counts.values()), "killed": counts[KILLED], "survived": counts[SURVIVED],
            "parse_failed": counts["PARSE_FAILED"], "error": counts["ERROR"],
            "emkr": round(counts[KILLED] / executable, 6) if executable else "",
            "changed_construct": entry.get("changed_construct", ""),
            "original": " ".join(str(entry.get("original", "")).split()),
            "mutated": " ".join(str(entry.get("mutated", "")).split()),
        })
    return rows


CROSSTAB_FIELDS = ("table", "row", "column", "language", "count")


def crosstab_rows(run_rows: Sequence[Mapping[str, object]], runs: Sequence[RunFacts],
                  evidence: Mapping[str, RunEvidence]) -> list[dict[str, object]]:
    """Long-format counts over diagnosis records and over run failure classes."""
    counts: Counter = Counter()
    rows_by_run = {row["run_id"]: row for row in run_rows}
    for run in runs:
        recovery = rows_by_run[run.run_id].get("semantic_final_full_pass") or "not_executed"
        routed_by_attempt: dict[int, set[str]] = {}
        for refinement in run.refinements:
            if refinement.purpose == SEMANTIC_REFINEMENT and refinement.source_execution_attempt is not None:
                routed_by_attempt.setdefault(refinement.source_execution_attempt, set()).add(refinement.artifact_type)
        for record in evidence[run.run_id].diagnoses:
            routed = "+".join(sorted(routed_by_attempt.get(record.execution_attempt, set()))) or "none"
            for table, column in (("diagnosis_x_language", run.language),
                                  ("diagnosis_x_final_recovery", f"final_full_pass={recovery}"),
                                  ("diagnosis_x_routed_artifact", routed)):
                counts[(table, record.classification, column, run.language)] += 1

    for row in run_rows:
        language = str(row["language"])
        if row.get("test_failure_reason"):
            counts[("rq1_final_suite_failure", row["test_failure_reason"],
                    row.get("test_failure_class", ""), language)] += 1
        if row.get("parser_failure_category"):
            counts[("rq2_unrepaired_parser_failure", row["parser_failure_category"],
                    row.get("parser_failure_error_kinds", ""), language)] += 1
        if row.get("parser_initial_category"):
            counts[("rq2_initial_parser_failure", row["parser_initial_category"],
                    "repaired" if row.get("syntax_post_pass") == "true" else "unrepaired", language)] += 1
        if row.get("semantic_population") in (RQ3_FAILED_NOT_REFINED, RQ3_FAILED_AFTER_REFINEMENT):
            counts[("rq3_unrecovered_reason", row["semantic_population"],
                    row.get("semantic_outcome_reason", ""), language)] += 1
            counts[("rq3_unrecovered_final_failure", row["semantic_population"],
                    row.get("semantic_final_failure_class", ""), language)] += 1
        if row.get("semantic_initial_failure_class"):
            counts[("rq3_initial_failure_class", row["semantic_initial_failure_class"],
                    row["semantic_population"], language)] += 1
        if row.get("test_initial_executable") and row.get("test_final_executable"):
            counts[("rq1_suite_executability_transition", f"initial_executable={row['test_initial_executable']}",
                    f"final_executable={row['test_final_executable']}", language)] += 1
        if row.get("semantic_population"):
            is_syntax_refined = int(row.get("syntax_refinement_count") or 0) > 0
            counts[("rq3_population_x_syntax_refinement", row["semantic_population"],
                    f"syntax_refined={_flag(is_syntax_refined)}", language)] += 1

    return [
        {"table": table, "row": row, "column": column, "language": language, "count": count}
        for (table, row, column, language), count in sorted(counts.items(), key=lambda item: tuple(map(str, item[0])))
    ]

def _group_metadata(selection_root: Path, group: EvaluationGroup) -> dict[str, dict[str, str]]:
    return {row["run_id"]: row for row in read_csv(selection_root / group.name / "batch-runs.csv")}


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise", restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if value is None else value for key, value in row.items()})
            count += 1
    temporary.replace(path)
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--selection-root", type=Path, default=DEFAULT_SELECTION_ROOT,
                        help="tree of evaluation groups (default: artifacts/Chosen_for_evaluation)")
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for the four CSV files")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        groups = discover_groups(args.selection_root)
        manifest = read_json_object(MUTANTS_MANIFEST)
        mutant_columns = sorted(manifest["operators"], key=lambda operator: int(operator.lstrip("M")))
        runs, evidence, rows, events = [], {}, [], []
        for group in groups:
            metadata = _group_metadata(args.selection_root, group)
            for batch_id, run_id in group.runs:
                run = read_run_facts(group, batch_id, run_id)
                try:
                    run_evidence = read_run_evidence(batch_id, run_id)
                except (KeyError, IndexError, ValueError) as exc:
                    raise EvaluationInputError(f"{batch_id}/{run_id}: unreadable evidence: {exc}") from exc
                runs.append(run)
                evidence[run_id] = run_evidence
                rows.append(run_row(run, run_evidence, metadata.get(run_id, {}), mutant_columns))
                events.extend(event_rows(run, run_evidence))
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    tasks = {run_id: run_evidence.task for run_id, run_evidence in evidence.items()}
    output = args.output_dir
    written = {
        "failure-runs.csv": write_csv(output / "failure-runs.csv", RUN_FIELDS, rows),
        "failure-events.csv": write_csv(output / "failure-events.csv", EVENT_FIELDS, events),
        "mutant-outcomes.csv": write_csv(output / "mutant-outcomes.csv", MUTANT_FIELDS,
                                         mutant_rows(runs, tasks, manifest)),
        "failure-crosstabs.csv": write_csv(output / "failure-crosstabs.csv", CROSSTAB_FIELDS,
                                           crosstab_rows(rows, runs, evidence)),
    }
    for name, count in written.items():
        print(f"wrote {count} rows to {output / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
