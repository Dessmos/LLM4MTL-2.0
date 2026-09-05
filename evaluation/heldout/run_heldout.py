"""Run one fixed held-out suite over every stored transformation iteration."""

from __future__ import annotations

import argparse
import json
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    preflight_runs,
    read_json_object,
    transformation_iterations,
    write_csv,
)
from llm4mtl.domain import GeneratedSuite, RawExecutionEvidence
from llm4mtl.languages import Workspace, language_adapter
from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_method_name
from llm4mtl.workspace import materialize_engine


FIELDNAMES = (
    "run_id",
    "language",
    "task",
    "evaluation_id",
    "iteration",
    "is_initial",
    "is_final",
    "test_id",
    "result",
    "failure_stage",
    "transformation_path",
)
RESULT_PRIORITY = {"PASS": 0, "NOT_RUN": 1, "FAIL": 2, "ERROR": 3}


@dataclass(frozen=True)
class HeldoutDefinition:
    """One immutable held-out suite and its stable semantic case ids."""

    evaluation_id: str
    source_dir: Path
    test_ids: tuple[str, ...]


def load_heldout_definition(
    tests_root: Path,
    language: str,
    task: str,
) -> HeldoutDefinition:
    """Load ``tests/<language>/<task>`` and require stable unique case names."""
    source_dir = tests_root.resolve() / language / task
    semantic_cases_path = source_dir / "semantic_cases.json"
    if not semantic_cases_path.is_file():
        raise EvaluationInputError(
            f"held-out semantic_cases.json is missing for {language}/{task}: "
            f"{semantic_cases_path}"
        )
    payload = read_json_object(semantic_cases_path)
    tests = payload.get("tests")
    if not isinstance(tests, list) or not tests:
        raise EvaluationInputError(f"held-out suite has no tests: {semantic_cases_path}")
    test_ids: list[str] = []
    for test in tests:
        if not isinstance(test, dict) or not isinstance(test.get("name"), str):
            raise EvaluationInputError(
                f"each held-out case needs a string name: {semantic_cases_path}"
            )
        test_id = str(test["name"])
        if not test_id:
            raise EvaluationInputError(f"held-out case name is empty: {semantic_cases_path}")
        test_ids.append(test_id)
    if len(set(test_ids)) != len(test_ids):
        raise EvaluationInputError(
            f"held-out case names must be unique: {semantic_cases_path}"
        )
    rendered_ids = [sanitize_method_name(test_id) for test_id in test_ids]
    if len(set(rendered_ids)) != len(rendered_ids):
        raise EvaluationInputError(
            f"held-out case names collide after Java rendering: {semantic_cases_path}"
        )
    metadata_path = source_dir / "metadata.json"
    evaluation_id = tests_root.resolve().name
    if metadata_path.is_file():
        metadata = read_json_object(metadata_path)
        if not isinstance(metadata.get("id"), str) or not metadata["id"]:
            raise EvaluationInputError(f"held-out metadata needs a non-empty id: {metadata_path}")
        evaluation_id = str(metadata["id"])
    return HeldoutDefinition(evaluation_id, source_dir, tuple(test_ids))


def classify_surefire_cases(
    evidence: RawExecutionEvidence,
    test_ids: Sequence[str],
) -> dict[str, str]:
    """Map archived Surefire testcase elements back to stable semantic case ids."""
    expected = {sanitize_method_name(test_id): test_id for test_id in test_ids}
    statuses: dict[str, str] = {}
    for artifact in evidence.reports:
        try:
            root = ET.fromstring(artifact.content)
        except ET.ParseError:
            continue
        for case in root.iter("testcase"):
            method_name = str(case.get("name") or "")
            test_id = expected.get(method_name)
            if test_id is None:
                continue
            status = _testcase_status(case)
            previous = statuses.get(test_id)
            if previous is None or RESULT_PRIORITY[status] > RESULT_PRIORITY[previous]:
                statuses[test_id] = status
    for test_id in test_ids:
        statuses.setdefault(test_id, "NOT_RUN")
    return statuses


def evaluate_runs(
    selected_runs: Sequence[SelectedRun],
    tests_root: Path,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Evaluate all selected runs without writing inside any run directory."""
    definitions = {
        (run.language, run.task): load_heldout_definition(
            tests_root, run.language, run.task
        )
        for run in selected_runs
    }
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="llm4mtl-heldout-") as temporary:
        temporary_root = Path(temporary)
        for selected_run in selected_runs:
            definition = definitions[(selected_run.language, selected_run.task)]
            rows.extend(
                _evaluate_run(
                    selected_run,
                    definition,
                    temporary_root / selected_run.run_id,
                    timeout_seconds,
                )
            )
    return rows


def _evaluate_run(
    selected_run: SelectedRun,
    definition: HeldoutDefinition,
    temporary_root: Path,
    timeout_seconds: int,
) -> Iterable[dict[str, Any]]:
    adapter = language_adapter(selected_run.language)
    extracted = {
        path.relative_to(definition.source_dir).as_posix(): path.read_text(
            encoding="utf-8"
        )
        for path in sorted(definition.source_dir.rglob("*"))
        if path.is_file() and path.name != "metadata.json"
    }
    rendered, validation = adapter.render_suite_artifacts(selected_run.task, extracted)
    if not validation.valid:
        raise EvaluationInputError(
            f"held-out suite is invalid for {selected_run.language}/{selected_run.task}: "
            + "; ".join(validation.violations)
        )
    suite_dir = temporary_root / "suite"
    for relative, content in rendered.items():
        destination = suite_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
    (suite_dir / "metadata.json").write_text(
        json.dumps({"artifact_validation": validation.as_metadata()}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    suite = GeneratedSuite(
        selected_run.language,
        suite_dir,
        selected_run.task,
        "heldout",
        definition.evaluation_id,
        f"{definition.evaluation_id}-{selected_run.language}-{selected_run.task}",
    )
    static_validation = adapter.validate_suite_artifacts(suite)
    if not static_validation.valid:
        raise EvaluationInputError(
            f"rendered held-out suite is invalid for {selected_run.run_id}: "
            + "; ".join(static_validation.violations)
        )
    engine_dir = materialize_engine(
        TARGET.engine_harness(selected_run.language),
        temporary_root / "workspaces",
        f"{selected_run.language}-harness",
    )
    iterations = transformation_iterations(selected_run)
    final_iteration = iterations[-1][0]
    for iteration, transformation in iterations:
        observation, evidence = adapter.execute_suite(
            suite,
            transformation,
            Workspace(
                engine_dir=engine_dir,
                observations_dir=temporary_root / "observations" / f"iteration-{iteration:03d}",
            ),
            timeout_seconds,
        )
        statuses = classify_surefire_cases(evidence, definition.test_ids)
        for test_id in definition.test_ids:
            status = statuses[test_id]
            if status == "NOT_RUN" and observation.failure_stage:
                status = "ERROR"
            yield {
                "run_id": selected_run.run_id,
                "language": selected_run.language,
                "task": selected_run.task,
                "evaluation_id": definition.evaluation_id,
                "iteration": iteration,
                "is_initial": str(iteration == 0).lower(),
                "is_final": str(iteration == final_iteration).lower(),
                "test_id": test_id,
                "result": status,
                "failure_stage": observation.failure_stage,
                "transformation_path": str(transformation),
            }


def _testcase_status(case: ET.Element) -> str:
    if case.find("error") is not None:
        return "ERROR"
    if case.find("failure") is not None:
        return "FAIL"
    if case.find("skipped") is not None:
        return "NOT_RUN"
    return "PASS"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=TARGET.runs)
    parser.add_argument("--run-ids", type=Path, required=True)
    parser.add_argument("--tests-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0:
        raise EvaluationInputError("--timeout-seconds must be positive")
    selected_runs = preflight_runs(args.runs_root, args.run_ids)
    rows = evaluate_runs(selected_runs, args.tests_root, args.timeout_seconds)
    write_csv(args.output, FIELDNAMES, rows)
    print(f"wrote {len(rows)} held-out observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
