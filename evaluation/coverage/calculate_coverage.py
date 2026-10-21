"""Calculate suite-level EClass coverage from stored models and task contracts."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import (
    EvaluationInputError,
    SelectedRun,
    preflight_runs,
    read_json_object,
    write_csv,
)
from llm4mtl.conventions import default_generated_tests_root, language_config
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.task_contracts import ModelContract, load_task_contract


FIELDNAMES = (
    "run_id",
    "language",
    "task",
    "suite_id",
    "covered_eclasses",
    "eligible_eclasses",
    "covered_count",
    "eligible_count",
    "coverage",
)
XSI_TYPE = "{http://www.w3.org/2001/XMLSchema-instance}type"
ECORE_CLASS = "{http://www.eclipse.org/emf/2002/Ecore}EClass"
ECORE_REFERENCE = "{http://www.eclipse.org/emf/2002/Ecore}EReference"


@dataclass(frozen=True)
class MetamodelShape:
    """Containment-feature types needed to classify nested XMI elements."""

    feature_types: Mapping[str, Mapping[str, str]]


def calculate_coverage_rows(
    selected_runs: Sequence[SelectedRun],
    generated_tests_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Calculate one static coverage observation per generated suite."""
    rows: list[dict[str, Any]] = []
    for selected_run in selected_runs:
        config = language_config(selected_run.language)
        if generated_tests_root is None:
            root = default_generated_tests_root(config).resolve()
        else:
            root = generated_tests_root.resolve() / selected_run.language
        candidates = _candidate_suites(selected_run, root)
        if not candidates:
            raise EvaluationInputError(
                f"no stored generated suites for selected run {selected_run.run_id}"
            )
        contract = load_task_contract(selected_run.task, config=config)
        if contract is None:
            raise EvaluationInputError(
                f"task contract is missing for {selected_run.language}/{selected_run.task}"
            )
        input_contracts = {
            model.runtime_name: model
            for model in contract.models
            if model.kind == "emf" and model.has_role("source")
        }
        eligible = {
            type_name
            for model in input_contracts.values()
            for type_name in model.types_used_in_transformation
        }
        shapes = {
            runtime_name: _load_metamodel_shape(model)
            for runtime_name, model in input_contracts.items()
        }
        for suite_dir in candidates:
            semantic_cases_path = suite_dir / "semantic_cases.json"
            covered: set[str] = set()
            if semantic_cases_path.is_file():
                semantic_cases = read_json_object(semantic_cases_path)
                covered = covered_eclasses(
                    semantic_cases,
                    suite_dir,
                    input_contracts,
                    shapes,
                    selected_run.language,
                )
            covered &= eligible
            denominator = len(eligible)
            rows.append(
                {
                    "run_id": selected_run.run_id,
                    "language": selected_run.language,
                    "task": selected_run.task,
                    "suite_id": suite_dir.name,
                    "covered_eclasses": ";".join(sorted(covered)),
                    "eligible_eclasses": ";".join(sorted(eligible)),
                    "covered_count": len(covered),
                    "eligible_count": denominator,
                    "coverage": "" if denominator == 0 else len(covered) / denominator,
                }
            )
    return rows


def covered_eclasses(
    semantic_cases: Mapping[str, Any],
    suite_dir: Path,
    input_contracts: Mapping[str, ModelContract],
    shapes: Mapping[str, MetamodelShape],
    language: str,
) -> set[str]:
    """Return classes instantiated in inputs plus Reactions change elements."""
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise EvaluationInputError(f"semantic cases has no tests list: {suite_dir}")
    covered: set[str] = set()
    for test in tests:
        if not isinstance(test, dict):
            raise EvaluationInputError(f"invalid semantic test in {suite_dir}")
        models = test.get("models")
        if not isinstance(models, list):
            raise EvaluationInputError(f"semantic test has no models list in {suite_dir}")
        for model in models:
            if not isinstance(model, dict) or model.get("role") not in {"source", "inout"}:
                continue
            runtime_name = str(model.get("runtimeName") or model.get("name") or "")
            contract = input_contracts.get(runtime_name)
            artifact = model.get("path")
            if contract is None or not isinstance(artifact, str):
                continue
            model_path = (suite_dir / artifact).resolve()
            try:
                model_path.relative_to(suite_dir.resolve())
            except ValueError as exc:
                raise EvaluationInputError(
                    f"model path escapes suite directory: {artifact}"
                ) from exc
            if not model_path.is_file():
                raise EvaluationInputError(f"input model does not exist: {model_path}")
            covered.update(_instances_in_model(model_path, shapes[runtime_name]))
        if language == "reactions":
            covered.update(_reaction_change_types(test))
    return covered


def _candidate_suites(selected_run: SelectedRun, generated_tests_root: Path) -> list[Path]:
    task_root = generated_tests_root / selected_run.task / "candidates"
    if not task_root.is_dir():
        return []
    candidates: list[Path] = []
    for metadata_path in sorted(task_root.glob("*/*/*/metadata.json")):
        metadata = read_json_object(metadata_path)
        if (
            metadata.get("language") == selected_run.language
            and metadata.get("task") == selected_run.task
            and str(metadata.get("suite_id") or "").startswith(
                selected_run.run_id + "_"
            )
        ):
            candidates.append(metadata_path.parent)
    return candidates


def _load_metamodel_shape(contract: ModelContract) -> MetamodelShape:
    if not contract.metamodel_file:
        return MetamodelShape({})
    metamodel_path = (REPO_ROOT / contract.metamodel_file).resolve()
    if not metamodel_path.is_file():
        raise EvaluationInputError(f"metamodel does not exist: {metamodel_path}")
    try:
        root = ET.parse(metamodel_path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise EvaluationInputError(f"cannot parse metamodel {metamodel_path}: {exc}") from exc
    feature_types: dict[str, dict[str, str]] = {}
    for classifier in root.iter():
        if classifier.get(XSI_TYPE) not in {"ecore:EClass", ECORE_CLASS}:
            continue
        class_name = classifier.get("name")
        if not class_name:
            continue
        features: dict[str, str] = {}
        for feature in classifier:
            feature_type = feature.get(XSI_TYPE)
            if feature_type not in {"ecore:EReference", ECORE_REFERENCE}:
                continue
            name = feature.get("name")
            target = feature.get("eType", "").split("#//")[-1]
            if name and target:
                features[name] = target
        feature_types[class_name] = features
    return MetamodelShape(feature_types)


def _instances_in_model(path: Path, shape: MetamodelShape) -> set[str]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise EvaluationInputError(f"cannot parse input model {path}: {exc}") from exc
    covered: set[str] = set()

    def visit(element: ET.Element, parent_type: str | None = None) -> None:
        xsi_type = element.get(XSI_TYPE)
        local_tag = _local_name(element.tag)
        if xsi_type:
            class_name = xsi_type.split(":")[-1]
        elif local_tag in shape.feature_types:
            class_name = local_tag
        elif parent_type is not None:
            class_name = shape.feature_types.get(parent_type, {}).get(local_tag, "")
        else:
            class_name = ""
        if class_name:
            covered.add(class_name)
        for child in element:
            visit(child, class_name or parent_type)

    visit(root)
    return covered


def _reaction_change_types(test: Mapping[str, Any]) -> set[str]:
    covered: set[str] = set()
    changes = test.get("changes")
    if not isinstance(changes, list):
        return covered
    for change in changes:
        if not isinstance(change, dict):
            continue
        target = change.get("target")
        value = change.get("value")
        if isinstance(target, dict) and isinstance(target.get("type"), str):
            covered.add(str(target["type"]))
        if isinstance(value, dict) and isinstance(value.get("type"), str):
            covered.add(str(value["type"]))
    return covered


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=None)
    parser.add_argument("--run-ids", type=Path, required=True)
    parser.add_argument("--generated-tests-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = preflight_runs(args.runs_root or TARGET.runs, args.run_ids)
    rows = calculate_coverage_rows(selected, args.generated_tests_root)
    write_csv(args.output, FIELDNAMES, rows)
    print(f"wrote {len(rows)} coverage observations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
