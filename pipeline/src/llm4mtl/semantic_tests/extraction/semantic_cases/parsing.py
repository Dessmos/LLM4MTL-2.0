"""Parse and validate semantic_cases.json into the canonical spec shape."""

from __future__ import annotations

import json
from typing import Any

from llm4mtl.artifact_schemas import ArtifactSchemaError, validate_artifact
from llm4mtl.semantic_tests.semantic_spec import SEMANTIC_CASES_FILE

from .errors import SemanticCasesError
from .legacy_adapter import is_legacy_tree2graph_spec, normalize_legacy_tree2graph_spec
from .normalization import normalize_schema_variants

SUPPORTED_ASSERTION_KINDS = frozenset(
    {
        "collectionSize",
        "count",
        "featureValues",
        "objects",
        "pathValues",
        "referencePairs",
        "treePaths",
    }
)


def parse_semantic_cases(
    raw_json: str,
    target_task: str,
    transformation_extension: str = ".etl",
) -> dict[str, Any]:
    try:
        spec = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SemanticCasesError(f"Invalid {SEMANTIC_CASES_FILE}: {exc}") from exc

    if not isinstance(spec, dict):
        raise SemanticCasesError(f"{SEMANTIC_CASES_FILE} must contain a JSON object")
    if is_legacy_tree2graph_spec(spec):
        spec = normalize_legacy_tree2graph_spec(spec)
    spec = normalize_schema_variants(
        spec,
        target_task,
        transformation_extension=transformation_extension,
    )
    validate_semantic_cases(spec, target_task)
    try:
        validate_artifact("semantic-cases", spec)
    except ArtifactSchemaError as exc:
        raise SemanticCasesError(str(exc)) from exc
    return spec


def validate_semantic_cases(spec: dict[str, Any], target_task: str) -> None:
    tests = spec.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SemanticCasesError(
            f"{SEMANTIC_CASES_FILE} must contain a non-empty tests array"
        )

    if "transformation" in spec and not isinstance(spec["transformation"], str):
        raise SemanticCasesError("transformation must be a string")
    if "metamodels" in spec and not isinstance(spec["metamodels"], list):
        raise SemanticCasesError("metamodels must be an array")
    if "models" in spec and not isinstance(spec["models"], list):
        raise SemanticCasesError("models must be an array")

    for index, test in enumerate(tests, start=1):
        _validate_semantic_test(test, spec, index)


def _validate_semantic_test(test: Any, spec: dict[str, Any], index: int) -> None:
    if not isinstance(test, dict):
        raise SemanticCasesError(
            f"{SEMANTIC_CASES_FILE} test #{index} must be an object"
        )
    if not test.get("name"):
        raise SemanticCasesError(f"{SEMANTIC_CASES_FILE} test #{index} is missing name")
    # Read raw rather than through `effective_models`, which copies each entry
    # into a dict: a string where a model object belongs must be an invalid
    # specification, not an unhandled coercion error from the extractor.
    models = test["models"] if "models" in test else spec.get("models", [])
    if not isinstance(models, list) or not models:
        raise SemanticCasesError(
            f"{SEMANTIC_CASES_FILE} test #{index} must define models"
        )
    validate_models(models, index)
    assertions = test.get("assertions")
    if not isinstance(assertions, list) or not assertions:
        raise SemanticCasesError(
            f"{SEMANTIC_CASES_FILE} test #{index} must define non-empty assertions"
        )
    validate_assertions(assertions, {str(model["name"]) for model in models}, index)


def validate_models(models: list[dict[str, Any]], test_index: int) -> None:
    for model_index, model in enumerate(models, start=1):
        _validate_model(model, test_index, model_index)


def _validate_model(model: Any, test_index: int, model_index: int) -> None:
    if not isinstance(model, dict):
        raise SemanticCasesError(
            f"test #{test_index} model #{model_index} must be an object"
        )
    if not model.get("name"):
        raise SemanticCasesError(
            f"test #{test_index} model #{model_index} is missing name"
        )
    kind = model.get("kind", "emf")
    if kind not in {"emf", "plainXml"}:
        raise SemanticCasesError(
            f"test #{test_index} model #{model_index} has unsupported kind: {kind}"
        )
    role = model.get("role", "source" if model.get("path") else "target")
    if role not in {"source", "target", "inout"}:
        raise SemanticCasesError(
            f"test #{test_index} model #{model_index} has unsupported role: {role}"
        )
    if role in {"source", "inout"} and not model.get("path"):
        raise SemanticCasesError(
            f"test #{test_index} readable model {model['name']} is missing path"
        )
    if kind == "emf" and not model.get("metamodelUri"):
        raise SemanticCasesError(
            f"test #{test_index} EMF model {model['name']} is missing metamodelUri"
        )


def validate_assertions(
    assertions: list[dict[str, Any]],
    model_names: set[str],
    test_index: int,
) -> None:
    for assertion_index, assertion in enumerate(assertions, start=1):
        _validate_assertion(assertion, model_names, test_index, assertion_index)


def _validate_assertion(
    assertion: Any,
    model_names: set[str],
    test_index: int,
    assertion_index: int,
) -> None:
    if not isinstance(assertion, dict):
        raise SemanticCasesError(
            f"test #{test_index} assertion #{assertion_index} must be an object"
        )
    kind = assertion.get("kind")
    if kind not in SUPPORTED_ASSERTION_KINDS:
        raise SemanticCasesError(
            f"test #{test_index} assertion #{assertion_index} "
            f"has unsupported kind: {kind}"
        )
    if assertion.get("model") not in model_names:
        raise SemanticCasesError(
            f"test #{test_index} assertion #{assertion_index} "
            "references an unknown model"
        )
    if not assertion.get("type"):
        raise SemanticCasesError(
            f"test #{test_index} assertion #{assertion_index} is missing type"
        )
    _validate_assertion_shape(assertion, str(kind), test_index, assertion_index)


def _validate_assertion_shape(
    assertion: dict[str, Any], kind: str, test_index: int, assertion_index: int
) -> None:
    if kind == "count":
        _validate_count_assertion(assertion, test_index, assertion_index)
    elif kind in {"featureValues", "pathValues"}:
        _validate_path_assertion(assertion, kind, test_index, assertion_index)
    elif kind == "treePaths":
        _validate_tree_paths_assertion(assertion, test_index, assertion_index)
    elif kind == "collectionSize":
        _validate_collection_size_assertion(assertion, test_index, assertion_index)
    elif kind == "objects":
        _validate_objects_assertion(assertion, test_index, assertion_index)
    elif kind == "referencePairs":
        _validate_reference_pairs_assertion(assertion, test_index, assertion_index)


def _validate_count_assertion(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    if not isinstance(assertion.get("expected"), int):
        raise SemanticCasesError(
            f"test #{test_index} count assertion #{assertion_index} "
            "must define integer expected"
        )


def _validate_path_assertion(
    assertion: dict[str, Any], kind: str, test_index: int, assertion_index: int
) -> None:
    field = "feature" if kind == "featureValues" else "path"
    if not assertion.get(field) or not isinstance(assertion.get("expected"), list):
        raise SemanticCasesError(
            f"test #{test_index} {kind} assertion #{assertion_index} is incomplete"
        )


def _validate_tree_paths_assertion(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    if not isinstance(assertion.get("expected"), list):
        raise SemanticCasesError(
            f"test #{test_index} treePaths assertion #{assertion_index} is incomplete"
        )


def _validate_collection_size_assertion(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    if (
        not assertion.get("path") or not isinstance(assertion.get("expected"), int)
    ):
        raise SemanticCasesError(
            f"test #{test_index} collectionSize assertion #{assertion_index} "
            "is incomplete"
        )


def _validate_objects_assertion(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    if not isinstance(assertion.get("features"), list) or not isinstance(
        assertion.get("expected"), list
    ):
        raise SemanticCasesError(
            f"test #{test_index} objects assertion #{assertion_index} is incomplete"
        )
    validate_object_expectations(assertion, test_index, assertion_index)


def _validate_reference_pairs_assertion(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    if (
        not assertion.get("source")
        or not assertion.get("target")
        or not isinstance(assertion.get("expected"), list)
    ):
        raise SemanticCasesError(
            f"test #{test_index} referencePairs assertion #{assertion_index} "
            "is incomplete"
        )
    validate_reference_pair_expectations(assertion, test_index, assertion_index)


def validate_reference_pair_expectations(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    """Every expected pair must name both endpoints.

    The harness derives the observed pairs by combining the values reachable
    along `source` and `target`, so an object whose target path yields nothing
    contributes no pair at all. An expectation with a null endpoint therefore
    cannot be satisfied by any model, and rendering it would only decide how the
    absence is spelled: Python renders `None`, one Java emitter renders `null`
    and the other the string "null". Nothing in the contract defines that value,
    so the specification is rejected rather than assigned a meaning here.
    """
    for pair_index, pair in enumerate(assertion["expected"], start=1):
        if not isinstance(pair, dict):
            raise SemanticCasesError(
                f"test #{test_index} referencePairs assertion #{assertion_index} "
                f"expected pair #{pair_index} must be an object with source and target"
            )
        for endpoint in ("source", "target"):
            if pair.get(endpoint) is None:
                raise SemanticCasesError(
                    f"test #{test_index} referencePairs assertion #{assertion_index} "
                    f"expected pair #{pair_index} has no {endpoint} identity; "
                    "a pair with a missing endpoint can never be observed"
                )


def validate_object_expectations(
    assertion: dict[str, Any], test_index: int, assertion_index: int
) -> None:
    """Every expected object must carry each declared feature with a value.

    The signature the harness compares is built from `features`, so an entry
    that omits one, or sets it to null, would be compared as the literal text of
    whatever the emitter happens to print for an absent value.
    """
    features = [str(feature) for feature in assertion["features"]]
    for object_index, expected in enumerate(assertion["expected"], start=1):
        if not isinstance(expected, dict):
            raise SemanticCasesError(
                f"test #{test_index} objects assertion #{assertion_index} "
                f"expected object #{object_index} must be an object"
            )
        for feature in features:
            if expected.get(feature) is None:
                raise SemanticCasesError(
                    f"test #{test_index} objects assertion #{assertion_index} "
                    f"expected object #{object_index} has no value for declared "
                    f"feature {feature!r}"
                )
