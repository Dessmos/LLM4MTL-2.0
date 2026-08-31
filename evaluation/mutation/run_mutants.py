"""Qualify mutants and run baseline/generated suites against them offline."""

from __future__ import annotations

import argparse
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    read_csv,
    write_csv,
)
from evaluation.mutation.generate_mutants import CATALOG_FIELDS
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
            workspace = workspaces.get(language)
            if workspace is None:
                engine_dir = materialize_engine(
                    TARGET.engine_harness(language),
                    root / "workspaces",
                    f"{language}-harness",
                )
                workspace = Workspace(engine_dir, root / "observations" / language)
                workspaces[language] = workspace
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--suites", type=Path, required=True)
    parser.add_argument("--qualified-catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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


if __name__ == "__main__":
    raise SystemExit(main())
