"""Schema-variant normalization: coerce LLM-authored spec shapes into the canonical form."""

from __future__ import annotations

from typing import Any

from llm4mtl.semantic_tests.semantic_spec import default_transformation, effective_models


def normalize_schema_variants(spec: dict[str, Any], target_task: str) -> dict[str, Any]:
    normalized = dict(spec)
    raw_metamodels = normalized.get("metamodels", [])
    normalized["transformation"] = normalize_transformation(normalized.get("transformation"), target_task)
    normalized["metamodels"] = normalize_metamodels(raw_metamodels)

    if "models" in normalized:
        normalized["models"] = normalize_models(normalized["models"])

    tests = []
    for test in normalized.get("tests", []):
        normalized_test = dict(test)
        normalized_test["models"] = normalize_models(effective_models(normalized, normalized_test))
        normalized_test["models"] = add_missing_target_models(
            normalized_test["models"],
            raw_metamodels,
        )
        normalized_test["assertions"] = [
            normalize_assertion(assertion, normalized_test["models"])
            for assertion in normalized_test.get("assertions", [])
        ]
        tests.append(normalized_test)
    normalized["tests"] = tests
    return normalized


def normalize_transformation(raw: Any, target_task: str) -> str:
    if isinstance(raw, str) and raw:
        return normalize_transformation_path(raw, target_task)
    if isinstance(raw, dict):
        for key in ("path", "module", "file"):
            if raw.get(key):
                return normalize_transformation_path(str(raw[key]), target_task)
        if raw.get("name"):
            return normalize_transformation_path(f"{raw['name']}.etl", target_task)
    return default_transformation(target_task)


def normalize_transformation_path(path: str, target_task: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if not normalized.endswith(".etl"):
        normalized = f"{normalized}.etl"
    if "/" not in normalized:
        normalized = f"transformations/{normalized}"
    return normalized


def normalize_metamodels(raw: Any) -> list[str]:
    paths: list[str] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict):
            if item.get("path"):
                paths.append(str(item["path"]))
            elif item.get("uri"):
                paths.append(f"metamodels/{item['uri']}.ecore")
            elif item.get("name"):
                paths.append(f"metamodels/{item['name']}.ecore")
    return paths


def normalize_models(raw: Any) -> list[dict[str, Any]]:
    models = []
    for model in raw if isinstance(raw, list) else []:
        if not isinstance(model, dict):
            continue
        normalized = dict(model)
        if isinstance(normalized.get("generated"), str):
            normalized["generated"] = True
        models.append(normalized)
    return models


def add_missing_target_models(models: list[dict[str, Any]], raw_metamodels: Any) -> list[dict[str, Any]]:
    existing_uris = {str(model.get("metamodelUri")) for model in models if model.get("metamodelUri")}
    augmented = list(models)
    for item in raw_metamodels if isinstance(raw_metamodels, list) else []:
        if not isinstance(item, dict):
            continue
        uri = str(item.get("uri") or item.get("name") or "")
        if not uri or uri in existing_uris:
            continue
        augmented.append(
            {
                "name": uri,
                "kind": "emf",
                "role": "target",
                "generated": False,
                "metamodelUri": uri,
            }
        )
        existing_uris.add(uri)
    return augmented


def normalize_assertion(assertion: Any, models: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(assertion, dict):
        return assertion
    normalized = dict(assertion)
    model_prefix, type_name = split_qualified_type(
        str(
            normalized.get("type")
            or normalized.get("fromType")
            or normalized.get("sourceType")
            or normalized.get("from")
            or normalized.get("reference")
            or ""
        )
    )
    if type_name:
        if normalized.get("kind") == "referencePairs" and "." in type_name:
            type_name, reference_feature = type_name.split(".", 1)
            normalized.setdefault("reference", reference_feature)
        normalized["type"] = type_name
    if "model" not in normalized and model_prefix:
        inferred = infer_model_name(models, model_prefix)
        if inferred:
            normalized["model"] = inferred
    if "model" not in normalized and type_name:
        inferred = infer_model_name(models, str(model_prefix or type_name))
        if inferred:
            normalized["model"] = inferred
    if "model" not in normalized:
        inferred = infer_default_assertion_model(models)
        if inferred:
            normalized["model"] = inferred

    if normalized.get("kind") == "pathValues" and "paths" in normalized:
        normalized["kind"] = "treePaths"
        normalized["expected"] = normalized["paths"]
    if normalized.get("kind") == "featureValues" and "size" in normalized and "where" in normalized:
        normalized["kind"] = "collectionSize"
        normalized["path"] = normalized.get("feature")
        normalized["expected"] = normalized["size"]
        normalized["where"] = normalize_object_match(normalized["where"])
        normalized["features"] = infer_object_features([normalized["where"]])
    if normalized.get("kind") == "referencePairs" and normalized.get("expectedTargetObjects") and normalized.get("sourceFeature"):
        normalized["kind"] = "pathValues"
        normalized["path"] = target_object_path(normalized["sourceFeature"], normalized["expectedTargetObjects"])
        normalized["expected"] = target_object_values(normalized["expectedTargetObjects"])
    if "expected" not in normalized:
        for key in ("equals", "values", "equalsSet", "value", "match", "where", "exact"):
            if key in normalized:
                if key == "exact" and isinstance(normalized[key], bool):
                    continue
                normalized["expected"] = normalized[key]
                break
    if normalized.get("kind") in {"featureValues", "pathValues"} and isinstance(normalized.get("expected"), list):
        normalized["expected"] = flatten_expected_values(normalized["expected"])
    if normalized.get("kind") == "objects":
        normalize_objects_assertion(normalized)
    if normalized.get("kind") == "featureValues" and "feature" not in normalized:
        if normalized.get("idFeature"):
            normalized["feature"] = normalized["idFeature"]
        elif isinstance(normalized.get("expected"), list) and normalized["expected"]:
            first = normalized["expected"][0]
            if isinstance(first, dict) and first.get("values") and isinstance(first["values"], dict):
                normalized["feature"] = next(iter(first["values"]))
                normalized["expected"] = [entry.get("values", {}).get(normalized["feature"]) for entry in normalized["expected"]]
    if normalized.get("kind") == "referencePairs":
        normalize_reference_pairs(normalized)
    if normalized.get("kind") in {"treePaths", "collectionSize"} and not normalized.get("type") and normalized.get("model"):
        model = model_by_name(models, str(normalized["model"]))
        if model and model.get("metamodelUri"):
            normalized["type"] = str(model["metamodelUri"])
    return normalized


def target_object_path(source_feature: Any, expected_targets: Any) -> str:
    feature = "value"
    for target in expected_targets if isinstance(expected_targets, list) else []:
        if isinstance(target, dict) and target:
            feature = str(next(iter(target)))
            break
    return f"{source_feature}.{feature}"


def target_object_values(expected_targets: Any) -> list[Any]:
    values = []
    for target in expected_targets if isinstance(expected_targets, list) else []:
        if isinstance(target, dict) and target:
            values.append(next(iter(target.values())))
    return values


def normalize_objects_assertion(assertion: dict[str, Any]) -> None:
    expected = assertion.get("expected")
    if isinstance(expected, dict):
        assertion["expected"] = [normalize_object_match(expected)]
        if "where" in assertion or "match" in assertion:
            assertion["contains"] = True
    elif expected is None:
        assertion["expected"] = []

    if "where" in assertion and "count" in assertion and isinstance(assertion["where"], dict):
        assertion["expected"] = [normalize_object_match(assertion["where"]) for _ in range(int(assertion["count"]))]
        assertion["contains"] = True
    elif "match" in assertion and "count" in assertion and isinstance(assertion["match"], dict):
        assertion["expected"] = [normalize_object_match(assertion["match"]) for _ in range(int(assertion["count"]))]
        assertion["contains"] = True

    if not isinstance(assertion.get("expected"), list):
        assertion["expected"] = []
    assertion["expected"] = [normalize_object_match(entry) for entry in assertion["expected"]]
    if "features" not in assertion:
        assertion["features"] = infer_object_features(assertion["expected"])


def normalize_object_match(match: Any) -> Any:
    if not isinstance(match, dict):
        return match
    if match.get("feature") and ("equals" in match or "value" in match):
        return {str(match["feature"]): match.get("equals", match.get("value"))}
    return match


def infer_object_features(expected: list[Any]) -> list[str]:
    features: list[str] = []
    for entry in expected:
        if not isinstance(entry, dict):
            continue
        values = entry.get("values") if isinstance(entry.get("values"), dict) else entry
        for key in values:
            if key not in features:
                features.append(str(key))
    return features


def normalize_reference_pairs(assertion: dict[str, Any]) -> None:
    if "source" not in assertion and assertion.get("sourceFeature"):
        assertion["source"] = assertion["sourceFeature"]
    if "target" not in assertion and assertion.get("targetFeature"):
        assertion["target"] = assertion["targetFeature"]
    if "expected" in assertion and isinstance(assertion["expected"], list):
        assertion["expected"] = normalize_pair_entries(assertion["expected"])
    elif "expected" not in assertion or not isinstance(assertion.get("expected"), list):
        if "equalsSet" in assertion:
            assertion["expected"] = [
                {"source": pair[0], "target": pair[1]}
                for pair in assertion["equalsSet"]
                if isinstance(pair, list) and len(pair) == 2
            ]
        elif "pairs" in assertion:
            assertion["expected"] = normalize_pair_entries(assertion["pairs"])

    id_feature = assertion.get("idFeature") or assertion.get("matchBy")
    if ("source" not in assertion or "target" not in assertion) and assertion.get("reference") and id_feature:
        _, reference_type = split_qualified_type(str(assertion.get("reference", "")))
        reference = reference_type or str(assertion["reference"]).split(".")[-1]
        assertion["source"] = assertion.get("source") or str(id_feature)
        assertion["target"] = assertion.get("target") or f"{reference}.{id_feature}"
    if ("source" not in assertion or "target" not in assertion) and assertion.get("reference"):
        reference = str(assertion["reference"]).split(".")[-1]
        id_path = str(assertion.get("idFeature") or assertion.get("matchBy") or "label")
        assertion["source"] = assertion.get("source") or id_path
        assertion["target"] = assertion.get("target") or f"{reference}.{id_path}"


def normalize_pair_entries(raw_pairs: Any) -> list[dict[str, str]]:
    pairs = []
    for pair in raw_pairs if isinstance(raw_pairs, list) else []:
        if isinstance(pair, list) and len(pair) == 2:
            pairs.append({"source": str(pair[0]), "target": str(pair[1])})
            continue
        if not isinstance(pair, dict):
            continue
        source = pair.get("source", pair.get("from", pair.get("sourceWhere")))
        target = pair.get("target", pair.get("to", pair.get("targetWhere")))
        pairs.append({"source": pair_endpoint_value(source), "target": pair_endpoint_value(target)})
    return pairs


def pair_endpoint_value(value: Any) -> str:
    if isinstance(value, dict):
        normalized = normalize_object_match(value)
        if isinstance(normalized, dict):
            for key in ("value", "id", "label", "name"):
                if key in normalized:
                    return str(normalized[key])
            if len(normalized) == 1:
                return str(next(iter(normalized.values())))
        return str(normalized)
    return str(value)


def flatten_expected_values(values: list[Any]) -> list[Any]:
    flattened = []
    for value in values:
        if isinstance(value, list):
            flattened.extend(value)
        else:
            flattened.append(value)
    return flattened


def split_qualified_type(type_value: str) -> tuple[str | None, str | None]:
    if "!" in type_value:
        model, type_name = type_value.split("!", 1)
        return model or None, type_name or None
    if "::" in type_value:
        model, type_name = type_value.split("::", 1)
        return model or None, type_name or None
    return None, type_value or None


def infer_model_name(models: list[dict[str, Any]], model_prefix: str) -> str | None:
    for role in ("target", "source"):
        for model in models:
            if model.get("role", "source" if model.get("path") else "target") != role:
                continue
            if model.get("name") == model_prefix or model.get("metamodelUri") == model_prefix:
                return str(model["name"])
    return None


def model_by_name(models: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for model in models:
        if str(model.get("name")) == name:
            return model
    return None


def infer_default_assertion_model(models: list[dict[str, Any]]) -> str | None:
    targets = [
        model
        for model in models
        if model.get("role", "source" if model.get("path") else "target") == "target"
    ]
    if len(targets) == 1:
        return str(targets[0]["name"])
    return None
