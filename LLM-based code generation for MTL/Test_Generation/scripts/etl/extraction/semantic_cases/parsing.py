"""Parse and validate semantic_cases.json into the canonical spec shape."""

from __future__ import annotations

import json
from typing import Any

from .legacy_adapter import is_legacy_tree2graph_spec, normalize_legacy_tree2graph_spec
from .normalization import normalize_schema_variants
from etl.semantic_spec import SEMANTIC_CASES_FILE, effective_models


def parse_semantic_cases(raw_json: str, target_task: str) -> dict[str, Any]:
    try:
        spec = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {SEMANTIC_CASES_FILE}: {exc}") from exc

    if not isinstance(spec, dict):
        raise SystemExit(f"{SEMANTIC_CASES_FILE} must contain a JSON object")
    if is_legacy_tree2graph_spec(spec):
        spec = normalize_legacy_tree2graph_spec(spec)
    spec = normalize_schema_variants(spec, target_task)
    validate_semantic_cases(spec, target_task)
    return spec


def validate_semantic_cases(spec: dict[str, Any], target_task: str) -> None:
    tests = spec.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SystemExit(f"{SEMANTIC_CASES_FILE} must contain a non-empty tests array")

    if "transformation" in spec and not isinstance(spec["transformation"], str):
        raise SystemExit("transformation must be a string")
    if "metamodels" in spec and not isinstance(spec["metamodels"], list):
        raise SystemExit("metamodels must be an array")
    if "models" in spec and not isinstance(spec["models"], list):
        raise SystemExit("models must be an array")

    for index, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} must be an object")
        if not test.get("name"):
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} is missing name")
        models = effective_models(spec, test)
        if not models:
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} must define models")
        validate_models(models, index)
        assertions = test.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} must define non-empty assertions")
        validate_assertions(assertions, {str(model["name"]) for model in models}, index)


def validate_models(models: list[dict[str, Any]], test_index: int) -> None:
    for model_index, model in enumerate(models, start=1):
        if not isinstance(model, dict):
            raise SystemExit(f"test #{test_index} model #{model_index} must be an object")
        if not model.get("name"):
            raise SystemExit(f"test #{test_index} model #{model_index} is missing name")
        kind = model.get("kind", "emf")
        if kind not in {"emf", "plainXml"}:
            raise SystemExit(f"test #{test_index} model #{model_index} has unsupported kind: {kind}")
        role = model.get("role", "source" if model.get("path") else "target")
        if role not in {"source", "target"}:
            raise SystemExit(f"test #{test_index} model #{model_index} has unsupported role: {role}")
        if role == "source" and not model.get("path"):
            raise SystemExit(f"test #{test_index} source model {model['name']} is missing path")
        if kind == "emf" and not model.get("metamodelUri"):
            raise SystemExit(f"test #{test_index} EMF model {model['name']} is missing metamodelUri")


def validate_assertions(assertions: list[dict[str, Any]], model_names: set[str], test_index: int) -> None:
    for assertion_index, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            raise SystemExit(f"test #{test_index} assertion #{assertion_index} must be an object")
        kind = assertion.get("kind")
        if kind not in {"count", "featureValues", "objects", "referencePairs", "pathValues", "treePaths", "collectionSize"}:
            raise SystemExit(f"test #{test_index} assertion #{assertion_index} has unsupported kind: {kind}")
        if assertion.get("model") not in model_names:
            raise SystemExit(f"test #{test_index} assertion #{assertion_index} references an unknown model")
        if not assertion.get("type"):
            raise SystemExit(f"test #{test_index} assertion #{assertion_index} is missing type")
        if kind == "count" and not isinstance(assertion.get("expected"), int):
            raise SystemExit(f"test #{test_index} count assertion #{assertion_index} must define integer expected")
        if kind in {"featureValues", "pathValues"}:
            field = "feature" if kind == "featureValues" else "path"
            if not assertion.get(field) or not isinstance(assertion.get("expected"), list):
                raise SystemExit(f"test #{test_index} {kind} assertion #{assertion_index} is incomplete")
        if kind == "treePaths" and not isinstance(assertion.get("expected"), list):
            raise SystemExit(f"test #{test_index} treePaths assertion #{assertion_index} is incomplete")
        if kind == "collectionSize":
            if not assertion.get("path") or not isinstance(assertion.get("expected"), int):
                raise SystemExit(f"test #{test_index} collectionSize assertion #{assertion_index} is incomplete")
        if kind == "objects":
            if not isinstance(assertion.get("features"), list) or not isinstance(assertion.get("expected"), list):
                raise SystemExit(f"test #{test_index} objects assertion #{assertion_index} is incomplete")
        if kind == "referencePairs":
            if not assertion.get("source") or not assertion.get("target") or not isinstance(assertion.get("expected"), list):
                raise SystemExit(f"test #{test_index} referencePairs assertion #{assertion_index} is incomplete")
