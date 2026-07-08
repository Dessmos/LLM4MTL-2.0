"""Generate deterministic Java tests from semantic-case artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from etl.contracts import enforce_contract, load_task_contract
from etl.suites.java import slug


SEMANTIC_CASES_FILE = "semantic_cases.json"
CONTRACT_VIOLATIONS_FILE = "contract_violations.json"


@dataclass(frozen=True)
class EnforcementOutcome:
    """Result of applying the task contract to a generated suite."""

    applied: bool
    valid: bool
    violations: list[str] = field(default_factory=list)


def can_generate_java_from_semantic_cases(target_task: str) -> bool:
    return True


def augment_with_generated_java(
    target_task: str,
    extracted: dict[str, str],
) -> tuple[dict[str, str], EnforcementOutcome]:
    cases_json = extracted.get(SEMANTIC_CASES_FILE)
    if not cases_json:
        return extracted, EnforcementOutcome(applied=False, valid=True)

    spec = parse_semantic_cases(cases_json, target_task)
    generated = dict(extracted)

    # Infrastructure bindings (metamodel URIs, runtime model names, ecore files,
    # XML namespaces) are owned by the task contract, not the LLM. Rewrite them
    # deterministically and reject assertions over undefined types.
    contract = load_task_contract(target_task)
    violations: list[str] = []
    if contract is not None:
        violations = enforce_contract(contract, spec, generated)
    outcome = EnforcementOutcome(
        applied=contract is not None,
        valid=not violations,
        violations=violations,
    )

    # Persist the normalized, contract-enforced spec for inspection.
    generated[SEMANTIC_CASES_FILE] = json.dumps(spec, indent=2) + "\n"

    # Plan B: semantic cases are the source of truth. Ignore any Java emitted by
    # the LLM and replace it with the deterministic harness.
    for path in list(generated):
        if path.endswith(".java"):
            del generated[path]

    if outcome.valid:
        class_name = sanitize_class_name(
            str(spec.get("testClass") or f"Generated{target_task}SemanticTest"),
            target_task,
        )
        generated[f"{class_name}.java"] = render_semantic_test(class_name, spec, target_task)
    else:
        # A contract-invalid suite must not reach Maven; record why instead of
        # emitting a harness that would fail with a cryptic EMF error.
        generated[CONTRACT_VIOLATIONS_FILE] = (
            json.dumps({"task": target_task, "violations": outcome.violations}, indent=2) + "\n"
        )

    return generated, outcome


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


def is_legacy_tree2graph_spec(spec: dict[str, Any]) -> bool:
    tests = spec.get("tests")
    return (
        isinstance(tests, list)
        and bool(tests)
        and "models" not in spec
        and any(isinstance(test, dict) and "expectedNodes" in test for test in tests)
    )


def normalize_legacy_tree2graph_spec(spec: dict[str, Any]) -> dict[str, Any]:
    tests = []
    for test in spec["tests"]:
        nodes = expected_node_names(test["expectedNodes"])
        edges = expected_edge_pairs(test["expectedEdges"])
        tests.append(
            {
                "name": test["name"],
                "models": [
                    {
                        "name": "Tree",
                        "kind": "emf",
                        "role": "source",
                        "path": test["inputModel"],
                        "generated": True,
                        "metamodelUri": "Tree",
                    },
                    {
                        "name": "Graph",
                        "kind": "emf",
                        "role": "target",
                        "metamodelUri": "Graph",
                    },
                ],
                "assertions": [
                    {"kind": "count", "model": "Graph", "type": "Node", "expected": len(nodes)},
                    {"kind": "count", "model": "Graph", "type": "Edge", "expected": len(edges)},
                    {
                        "kind": "featureValues",
                        "model": "Graph",
                        "type": "Node",
                        "feature": "name",
                        "expected": nodes,
                    },
                    {
                        "kind": "referencePairs",
                        "model": "Graph",
                        "type": "Edge",
                        "source": "source.name",
                        "target": "target.name",
                        "expected": [{"source": edge.split("->", 1)[0], "target": edge.split("->", 1)[1]} for edge in edges],
                    },
                ],
            }
        )

    return {
        "schemaVersion": 1,
        "testClass": spec.get("testClass") or "GeneratedTree2GraphSemanticTest",
        "transformation": "transformations/Tree2Graph.etl",
        "metamodels": ["metamodels/Tree.ecore", "metamodels/Graph.ecore"],
        "tests": tests,
    }


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


def render_semantic_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    methods = [render_test_method(spec, test, task) for test in spec["tests"]]
    metamodels = metamodel_paths(spec.get("metamodels", []))

    return "\n".join(
        [
            "package org.eclipse.epsilon.examples.etl.generated;",
            "",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            "import java.io.File;",
            "import java.util.ArrayList;",
            "import java.util.Arrays;",
            "import java.util.Collection;",
            "import java.util.LinkedHashMap;",
            "import java.util.List;",
            "import java.util.Map;",
            "",
            "import org.eclipse.emf.ecore.EObject;",
            "import org.eclipse.emf.ecore.EStructuralFeature;",
            "import org.eclipse.epsilon.emc.emf.EmfModel;",
            "import org.eclipse.epsilon.emc.plainxml.PlainXmlModel;",
            "import org.eclipse.epsilon.eol.models.IModel;",
            "import org.eclipse.epsilon.examples.etl.EtlTestBase;",
            "import org.junit.jupiter.api.BeforeEach;",
            "import org.junit.jupiter.api.Test;",
            "",
            f"public class {class_name} extends EtlTestBase {{",
            f'    private static final String ETL = "{escape_java(str(spec.get("transformation") or default_transformation(task)))}";',
            "",
            "    @BeforeEach",
            "    public void setUpGeneratedMetamodels() throws Exception {",
            *[f'        registerMetamodel("{escape_java(path)}");' for path in metamodels],
            "    }",
            "",
            *methods,
            *java_helpers(),
            "}",
            "",
        ]
    )


def render_test_method(spec: dict[str, Any], test: dict[str, Any], task: str) -> str:
    method_name = sanitize_method_name(str(test["name"]))
    models = effective_models(spec, test)
    model_vars = {str(model["name"]): f"model{index}" for index, model in enumerate(models)}
    lines = [
        "    @Test",
        f"    public void {method_name}() throws Exception {{",
        "        List<IModel> generatedModels = new ArrayList<>();",
    ]

    for index, model in enumerate(models):
        lines.extend(render_model_creation(model, f"model{index}", task))
        lines.append(f"        generatedModels.add(model{index});")

    lines.append("        runEtl(ETL, generatedModels.toArray(new IModel[0]));")
    for assertion in test["assertions"]:
        lines.extend(render_assertion(assertion, model_vars))
    lines.extend(["    }", ""])
    return "\n".join(lines)


def render_model_creation(model: dict[str, Any], var_name: str, task: str) -> list[str]:
    name = str(model["name"])
    kind = model.get("kind", "emf")
    role = model.get("role", "source" if model.get("path") else "target")
    if kind == "plainXml":
        return render_plain_xml_model(model, var_name, role, task)
    return render_emf_model(model, var_name, role, task)


def render_emf_model(model: dict[str, Any], var_name: str, role: str, task: str) -> list[str]:
    name = escape_java(runtime_model_name(model))
    metamodel_uri = escape_java(str(model["metamodelUri"]))
    read_on_load = java_bool(model.get("readOnLoad", role == "source"))
    store_on_disposal = java_bool(model.get("storeOnDisposal", role == "target"))
    if role == "source":
        path = model_resource_path(str(model["path"]), task, bool(model.get("generated", True)))
        return [
            f'        EmfModel {var_name} = createEmfModel("{name}", "{escape_java(path)}", "{metamodel_uri}", {read_on_load}, {store_on_disposal});'
        ]

    extension = str(model.get("fileExtension") or ".model")
    return [
        f'        File {var_name}File = File.createTempFile("{safe_temp_prefix(name)}_", "{escape_java(extension)}");',
        f"        {var_name}File.deleteOnExit();",
        f'        EmfModel {var_name} = createEmfModelFromFile("{name}", {var_name}File.getAbsolutePath(), "{metamodel_uri}", {read_on_load}, {store_on_disposal});',
    ]


def render_plain_xml_model(model: dict[str, Any], var_name: str, role: str, task: str) -> list[str]:
    name = escape_java(runtime_model_name(model))
    read_on_load = java_bool(model.get("readOnLoad", role == "source"))
    store_on_disposal = java_bool(model.get("storeOnDisposal", role == "target"))
    lines = [f"        PlainXmlModel {var_name} = new PlainXmlModel();", f'        {var_name}.setName("{name}");']
    if role == "source":
        path = model_resource_path(str(model["path"]), task, bool(model.get("generated", True)))
        lines.append(f'        {var_name}.setFile(new File(getResourcePath("{escape_java(path)}")));')
    else:
        extension = str(model.get("fileExtension") or ".xml")
        lines.extend(
            [
                f'        File {var_name}File = File.createTempFile("{safe_temp_prefix(name)}_", "{escape_java(extension)}");',
                f"        {var_name}File.deleteOnExit();",
                f"        {var_name}.setFile({var_name}File);",
            ]
        )
    lines.extend(
        [
            f"        {var_name}.setReadOnLoad({read_on_load});",
            f"        {var_name}.setStoredOnDisposal({store_on_disposal});",
            f"        {var_name}.load();",
        ]
    )
    return lines


def runtime_model_name(model: dict[str, Any]) -> str:
    for key in ("runtimeName", "modelName", "alias", "metamodelAlias"):
        if model.get(key):
            return str(model[key])
    if model.get("kind", "emf") == "emf" and model.get("metamodelUri"):
        return str(model["metamodelUri"])
    return str(model["name"])


def render_assertion(assertion: dict[str, Any], model_vars: dict[str, str]) -> list[str]:
    model_var = model_vars[str(assertion["model"])]
    kind = assertion["kind"]
    type_name = escape_java(str(assertion["type"]))
    message = escape_java(str(assertion.get("message") or f"{kind} assertion for {assertion['model']}::{assertion['type']}"))

    if kind == "count":
        return [
            f'        assertEquals({int(assertion["expected"])}, allOfType({model_var}, "{type_name}").size(), "{message}");'
        ]
    if kind == "featureValues":
        expected = java_string_list([str(value) for value in assertion["expected"]])
        feature = escape_java(str(assertion["feature"]))
        actual = f'pathValues({model_var}, "{type_name}", "{feature}")'
        return render_count_assertion(expected, actual, assertion, message)
    if kind == "pathValues":
        expected = java_string_list([str(value) for value in assertion["expected"]])
        path = escape_java(str(assertion["path"]))
        actual = f'pathValues({model_var}, "{type_name}", "{path}")'
        return render_count_assertion(expected, actual, assertion, message)
    if kind == "treePaths":
        expected = java_string_list([str(value) for value in assertion["expected"]])
        label_feature = escape_java(str(assertion.get("labelFeature") or "label"))
        children_feature = escape_java(str(assertion.get("childrenFeature") or "children"))
        actual = f'treePaths({model_var}, "{type_name}", "{label_feature}", "{children_feature}")'
        return render_count_assertion(expected, actual, assertion, message)
    if kind == "collectionSize":
        where = assertion.get("where") if isinstance(assertion.get("where"), dict) else {}
        features = list(where) if where else []
        expected_signature = object_signatures([where], features)[0] if features else ""
        path = escape_java(str(assertion["path"]))
        return [
            f'        assertCollectionSize({model_var}, "{type_name}", {java_string_array(features)}, "{escape_java(expected_signature)}", "{path}", {int(assertion["expected"])}, "{message}");'
        ]
    if kind == "objects":
        features = [str(feature) for feature in assertion["features"]]
        expected = object_signatures(assertion["expected"], features)
        actual = f'signaturesOf({model_var}, "{type_name}", {java_string_array(features)})'
        return render_count_assertion(java_string_list(expected), actual, assertion, message)
    if kind == "referencePairs":
        expected = [f"{pair['source']}->{pair['target']}" for pair in assertion["expected"]]
        source = escape_java(str(assertion["source"]))
        target = escape_java(str(assertion["target"]))
        actual = f'referencePairs({model_var}, "{type_name}", "{source}", "{target}")'
        return render_count_assertion(java_string_list(expected), actual, assertion, message)
    raise AssertionError(f"Unsupported assertion kind: {kind}")


def render_count_assertion(expected: str, actual: str, assertion: dict[str, Any], message: str) -> list[str]:
    if assertion.get("contains") is True:
        return [f'        assertContainsCounts({expected}, {actual}, "{message}");']
    return [f'        assertEquals(counts({expected}), counts({actual}), "{message}");']


def java_helpers() -> list[str]:
    return [
        "    private Collection<?> allOfType(IModel model, String typeName) throws Exception {",
        "        return model.getAllOfType(typeName);",
        "    }",
        "",
        "    private List<String> pathValues(IModel model, String typeName, String path) throws Exception {",
        "        List<String> values = new ArrayList<>();",
        "        for (Object object : allOfType(model, typeName)) {",
        "            for (Object value : pathValuesFrom(object, path)) {",
        "                values.add(stringValue(value));",
        "            }",
        "        }",
        "        return values;",
        "    }",
        "",
        "    private List<String> referencePairs(IModel model, String typeName, String sourcePath, String targetPath) throws Exception {",
        "        List<String> pairs = new ArrayList<>();",
        "        for (Object object : allOfType(model, typeName)) {",
        "            List<Object> sources = pathValuesFrom(object, sourcePath);",
        "            List<Object> targets = pathValuesFrom(object, targetPath);",
        "            for (Object source : sources) {",
        "                for (Object target : targets) {",
        "                    pairs.add(stringValue(source) + \"->\" + stringValue(target));",
        "                }",
        "            }",
        "        }",
        "        return pairs;",
        "    }",
        "",
        "    private List<String> treePaths(IModel model, String typeName, String labelFeature, String childrenFeature) throws Exception {",
        "        List<String> paths = new ArrayList<>();",
        "        for (Object object : allOfType(model, typeName)) {",
        "            if (object instanceof EObject && ((EObject) object).eContainer() == null) {",
        "                collectTreePaths(object, \"\", labelFeature, childrenFeature, paths);",
        "            }",
        "        }",
        "        return paths;",
        "    }",
        "",
        "    private void collectTreePaths(Object object, String prefix, String labelFeature, String childrenFeature, List<String> paths) {",
        "        String currentPath = prefix + \"/\" + stringValue(pathValue(object, labelFeature));",
        "        paths.add(currentPath);",
        "        for (Object child : pathValuesFrom(object, childrenFeature)) {",
        "            collectTreePaths(child, currentPath, labelFeature, childrenFeature, paths);",
        "        }",
        "    }",
        "",
        "    private List<String> signaturesOf(IModel model, String typeName, String[] features) throws Exception {",
        "        List<String> signatures = new ArrayList<>();",
        "        for (Object object : allOfType(model, typeName)) {",
        "            List<String> parts = new ArrayList<>();",
        "            for (String feature : features) {",
        "                parts.add(feature + \"=\" + stringValue(pathValue(object, feature)));",
        "            }",
        "            signatures.add(String.join(\"|\", parts));",
        "        }",
        "        return signatures;",
        "    }",
        "",
        "    private void assertCollectionSize(IModel model, String typeName, String[] features, String expectedSignature, String path, int expectedSize, String message) throws Exception {",
        "        boolean matched = false;",
        "        for (Object object : allOfType(model, typeName)) {",
        "            if (expectedSignature.equals(signatureOf(object, features))) {",
        "                matched = true;",
        "                assertEquals(expectedSize, pathValuesFrom(object, path).size(), message);",
        "            }",
        "        }",
        "        assertTrue(matched, message + \" missing object \" + expectedSignature);",
        "    }",
        "",
        "    private String signatureOf(Object object, String[] features) {",
        "        List<String> parts = new ArrayList<>();",
        "        for (String feature : features) {",
        "            parts.add(feature + \"=\" + stringValue(pathValue(object, feature)));",
        "        }",
        "        return String.join(\"|\", parts);",
        "    }",
        "",
        "    private Object pathValue(Object object, String path) {",
        "        Object current = object;",
        "        for (String part : path.split(\"\\\\.\")) {",
        "            current = featureValue(current, part);",
        "            if (current == null) {",
        "                return null;",
        "            }",
        "        }",
        "        return current;",
        "    }",
        "",
        "    private List<Object> pathValuesFrom(Object object, String path) {",
        "        List<Object> values = new ArrayList<>();",
        "        if (path == null || path.isEmpty()) {",
        "            addFlattened(values, object);",
        "            return values;",
        "        }",
        "        int dot = path.indexOf('.');",
        "        String first = dot >= 0 ? path.substring(0, dot) : path;",
        "        String rest = dot >= 0 ? path.substring(dot + 1) : \"\";",
        "        List<Object> currentValues = new ArrayList<>();",
        "        addFlattened(currentValues, object);",
        "        for (Object current : currentValues) {",
        "            Object next = featureValue(current, first);",
        "            if (rest.isEmpty()) {",
        "                addFlattened(values, next);",
        "            }",
        "            else {",
        "                values.addAll(pathValuesFrom(next, rest));",
        "            }",
        "        }",
        "        return values;",
        "    }",
        "",
        "    private void addFlattened(List<Object> values, Object value) {",
        "        if (value instanceof Collection<?>) {",
        "            values.addAll((Collection<?>) value);",
        "        }",
        "        else if (value != null) {",
        "            values.add(value);",
        "        }",
        "    }",
        "",
        "    private Object featureValue(Object object, String featureName) {",
        "        if (object instanceof EObject) {",
        "            EObject eObject = (EObject) object;",
        "            EStructuralFeature feature = eObject.eClass().getEStructuralFeature(featureName);",
        "            assertNotNull(feature, \"Missing feature \" + featureName + \" on \" + eObject.eClass().getName());",
        "            return eObject.eGet(feature);",
        "        }",
        "        fail(\"Feature assertions are only supported for EMF EObject instances: \" + object);",
        "        return null;",
        "    }",
        "",
        "    private String stringValue(Object value) {",
        "        return value == null ? null : String.valueOf(value);",
        "    }",
        "",
        "    private Map<String, Integer> counts(Collection<String> values) {",
        "        Map<String, Integer> counts = new LinkedHashMap<>();",
        "        for (String value : values) {",
        "            counts.put(value, counts.getOrDefault(value, 0) + 1);",
        "        }",
        "        return counts;",
        "    }",
        "",
        "    private void assertContainsCounts(Collection<String> expected, Collection<String> actual, String message) {",
        "        Map<String, Integer> actualCounts = counts(actual);",
        "        for (Map.Entry<String, Integer> expectedEntry : counts(expected).entrySet()) {",
        "            assertTrue(actualCounts.getOrDefault(expectedEntry.getKey(), 0) >= expectedEntry.getValue(), message + \" missing \" + expectedEntry.getKey());",
        "        }",
        "    }",
        "",
        "    private List<String> list(String... values) {",
        "        return Arrays.asList(values);",
        "    }",
        "",
    ]


def effective_models(spec: dict[str, Any], test: dict[str, Any]) -> list[dict[str, Any]]:
    models = test.get("models", spec.get("models", []))
    return [dict(model) for model in models]


def metamodel_paths(raw: Any) -> list[str]:
    paths = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
    return paths


def default_transformation(task: str) -> str:
    return f"transformations/{task}.etl"


def model_resource_path(path: str, task: str, generated: bool) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    if not generated:
        return normalized
    if normalized.startswith("models/"):
        normalized = normalized[len("models/") :]
    return f"generated-models/{slug(task)}/{normalized}"


def object_signatures(raw_objects: list[Any], features: list[str]) -> list[str]:
    signatures = []
    for raw_object in raw_objects:
        if not isinstance(raw_object, dict):
            raise SystemExit("objects assertion expected entries must be objects")
        parts = [f"{feature}={raw_object.get(feature)}" for feature in features]
        signatures.append("|".join(parts))
    return signatures


def expected_node_names(raw_nodes: Any) -> list[str]:
    if not isinstance(raw_nodes, list):
        raise SystemExit("expectedNodes must be an array")
    names: list[str] = []
    for node in raw_nodes:
        if isinstance(node, str):
            names.append(node)
        elif isinstance(node, dict) and isinstance(node.get("name"), str):
            names.append(node["name"])
        else:
            raise SystemExit("expectedNodes entries must be strings or objects with a name")
    return names


def expected_edge_pairs(raw_edges: Any) -> list[str]:
    if not isinstance(raw_edges, list):
        raise SystemExit("expectedEdges must be an array")
    pairs: list[str] = []
    for edge in raw_edges:
        if not isinstance(edge, dict) or not edge.get("source") or not edge.get("target"):
            raise SystemExit("expectedEdges entries must contain source and target")
        pairs.append(f"{edge['source']}->{edge['target']}")
    return pairs


def java_string_list(values: list[str]) -> str:
    escaped = ", ".join(f'"{escape_java(value)}"' for value in values)
    return f"list({escaped})" if values else "new ArrayList<>()"


def java_string_array(values: list[str]) -> str:
    escaped = ", ".join(f'"{escape_java(value)}"' for value in values)
    return f"new String[] {{{escaped}}}"


def java_bool(value: Any) -> str:
    return "true" if bool(value) else "false"


def safe_temp_prefix(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return cleaned if len(cleaned) >= 3 else f"{cleaned}_model"


def sanitize_class_name(value: str, task: str) -> str:
    value = value.split(".")[-1]
    value = value.removesuffix(".java")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value)
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned[0]):
        return f"Generated{sanitize_class_name(task, 'ETL')}SemanticTest"
    return cleaned


def sanitize_method_name(value: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", value)
    words = [part for part in parts if part]
    if not words:
        return "generatedSemanticCase"
    first, *rest = words
    method = first[:1].lower() + first[1:] + "".join(word[:1].upper() + word[1:] for word in rest)
    if not re.match(r"[A-Za-z_]", method[0]):
        method = f"case{method}"
    return method


def escape_java(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
