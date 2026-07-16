"""Render a deterministic JUnit Java harness from a canonical semantic-case spec."""

from __future__ import annotations

from typing import Any

from etl.codegen.helpers import (
    escape_java,
    java_bool,
    java_string_array,
    java_string_list,
    safe_temp_prefix,
    sanitize_method_name,
)
from etl.semantic_spec import default_transformation, effective_models
from etl.suites.java import slug


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


def metamodel_paths(raw: Any) -> list[str]:
    paths = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
    return paths


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
