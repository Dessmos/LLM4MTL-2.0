"""Deterministic reflective EMF assertions for generated Java harnesses."""

from __future__ import annotations

from typing import Any

from llm4mtl.semantic_tests.codegen.java import object_signatures
from llm4mtl.semantic_tests.codegen.java_rendering import (
    assertion_message,
    escape_java,
    java_string_array,
    java_string_list,
)

ALL_OF_TYPE_LOOP = "        for (EObject object : allOfType(roots, typeName)) {"


def render_assertions(
    assertions: list[dict[str, Any]],
    model_variables: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    for assertion in assertions:
        lines.extend(_render_assertion(assertion, model_variables))
    return lines


def _render_assertion(
    assertion: dict[str, Any],
    model_variables: dict[str, str],
) -> list[str]:
    model = model_variables[str(assertion["model"])]
    kind = str(assertion["kind"])
    type_name = escape_java(str(assertion["type"]))
    # The unescaped text is the shared rule; escaping it is this emitter's job.
    message = escape_java(assertion_message(assertion))
    match kind:
        case "count":
            return [
                f'        assertEquals({int(assertion["expected"])}, allOfType({model}, "{type_name}").size(), "{message}");'
            ]
        case "featureValues" | "pathValues" | "treePaths":
            return _render_path_collection_assertion(
                assertion,
                model,
                kind,
                type_name,
                message,
            )
        case "collectionSize" | "objects" | "referencePairs":
            return _render_object_collection_assertion(
                assertion,
                model,
                kind,
                type_name,
                message,
            )
        case _:
            raise ValueError(f"unsupported assertion kind: {kind}")


def _render_path_collection_assertion(
    assertion: dict[str, Any],
    model: str,
    kind: str,
    type_name: str,
    message: str,
) -> list[str]:
    expected = java_string_list([str(value) for value in assertion["expected"]])
    if kind in {"featureValues", "pathValues"}:
        path_key = "feature" if kind == "featureValues" else "path"
        path = escape_java(str(assertion[path_key]))
        actual = f'pathValues({model}, "{type_name}", "{path}")'
    else:
        label = escape_java(str(assertion.get("labelFeature") or "label"))
        children = escape_java(
            str(assertion.get("childrenFeature") or "children")
        )
        actual = f'treePaths({model}, "{type_name}", "{label}", "{children}")'
    return _collection_assertion(expected, actual, assertion, message)


def _render_object_collection_assertion(
    assertion: dict[str, Any],
    model: str,
    kind: str,
    type_name: str,
    message: str,
) -> list[str]:
    match kind:
        case "collectionSize":
            return _render_collection_size_assertion(
                assertion,
                model,
                type_name,
                message,
            )
        case "objects":
            return _render_objects_assertion(
                assertion,
                model,
                type_name,
                message,
            )
        case _:
            return _render_reference_pairs_assertion(
                assertion,
                model,
                type_name,
                message,
            )


def _render_collection_size_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    where = (
        assertion.get("where")
        if isinstance(assertion.get("where"), dict)
        else {}
    )
    features = [str(feature) for feature in where]
    expected_signature = object_signatures([where], features)[0] if features else ""
    path = escape_java(str(assertion["path"]))
    return [
        f'        assertCollectionSize({model}, "{type_name}", {java_string_array(features)}, '
        f'"{escape_java(expected_signature)}", "{path}", {int(assertion["expected"])}, "{message}");'
    ]


def _render_objects_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    features = [str(feature) for feature in assertion["features"]]
    expected = object_signatures(assertion["expected"], features)
    actual = (
        f'signaturesOf({model}, "{type_name}", '
        f"{java_string_array(features)})"
    )
    return _collection_assertion(
        java_string_list(expected),
        actual,
        assertion,
        message,
    )


def _render_reference_pairs_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    expected = [
        f"{pair['source']}->{pair['target']}"
        for pair in assertion["expected"]
    ]
    source = escape_java(str(assertion["source"]))
    target = escape_java(str(assertion["target"]))
    actual = f'referencePairs({model}, "{type_name}", "{source}", "{target}")'
    return _collection_assertion(
        java_string_list(expected),
        actual,
        assertion,
        message,
    )


def _collection_assertion(
    expected: str,
    actual: str,
    assertion: dict[str, Any],
    message: str,
) -> list[str]:
    if assertion.get("contains") is True:
        return [f'        assertContainsCounts({expected}, {actual}, "{message}");']
    return [f'        assertEquals(counts({expected}), counts({actual}), "{message}");']


def imports() -> list[str]:
    return [
        "import static org.junit.jupiter.api.Assertions.*;",
        "",
        "import java.util.ArrayList;",
        "import java.util.Collection;",
        "import java.util.LinkedHashMap;",
        "import java.util.List;",
        "import java.util.Map;",
        "import java.nio.file.Files;",
        "import java.nio.file.Path;",
        "",
        "import org.eclipse.emf.common.util.URI;",
        "import org.eclipse.emf.common.util.TreeIterator;",
        "import org.eclipse.emf.ecore.EObject;",
        "import org.eclipse.emf.ecore.EStructuralFeature;",
        "import org.eclipse.emf.ecore.util.EcoreUtil;",
        "import org.eclipse.emf.ecore.resource.Resource;",
        "import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;",
        "import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;",
    ]


def helpers() -> list[str]:
    """Java helpers operating on canonical lists of EMF roots."""
    return [
        # `relativePath` is `<test-case>/<model-slot>.xmi`, so the snapshot is
        # identified by the execution that produced it down to the case and the
        # slot. Creating the parent rather than the configured root is what lets
        # the case be a directory.
        "    private void writeSnapshot(String relativePath, List<EObject> roots) throws Exception {",
        "        String configured = System.getProperty(\"llm4mtl.observations.dir\", \"\");",
        "        if (configured.isBlank()) return;",
        "        Path target = Path.of(configured).resolve(relativePath);",
        "        Files.createDirectories(target.getParent());",
        "        ResourceSetImpl resourceSet = new ResourceSetImpl();",
        "        resourceSet.getResourceFactoryRegistry().getExtensionToFactoryMap().put(\"xmi\", new XMIResourceFactoryImpl());",
        "        Resource resource = resourceSet.createResource(URI.createFileURI(target.toString()));",
        "        resource.getContents().addAll(EcoreUtil.copyAll(roots));",
        "        resource.save(Map.of());",
        "    }",
        "",
        "    private List<EObject> allOfType(List<EObject> roots, String typeName) {",
        "        List<EObject> matches = new ArrayList<>();",
        "        for (EObject root : roots) {",
        "            if (root.eClass().getName().equals(typeName)) matches.add(root);",
        "            TreeIterator<EObject> iterator = root.eAllContents();",
        "            while (iterator.hasNext()) {",
        "                EObject object = iterator.next();",
        "                if (object.eClass().getName().equals(typeName)) matches.add(object);",
        "            }",
        "        }",
        "        return matches;",
        "    }",
        "",
        "    private List<String> pathValues(List<EObject> roots, String typeName, String path) {",
        "        List<String> values = new ArrayList<>();",
        ALL_OF_TYPE_LOOP,
        "            for (Object value : pathValuesFrom(object, path)) values.add(stringValue(value));",
        "        }",
        "        return values;",
        "    }",
        "",
        "    private List<String> referencePairs(List<EObject> roots, String typeName, String sourcePath, String targetPath) {",
        "        List<String> pairs = new ArrayList<>();",
        ALL_OF_TYPE_LOOP,
        "            for (Object source : pathValuesFrom(object, sourcePath)) {",
        "                for (Object target : pathValuesFrom(object, targetPath)) {",
        "                    pairs.add(stringValue(source) + \"->\" + stringValue(target));",
        "                }",
        "            }",
        "        }",
        "        return pairs;",
        "    }",
        "",
        "    private List<String> treePaths(List<EObject> roots, String typeName, String labelFeature, String childrenFeature) {",
        "        List<String> paths = new ArrayList<>();",
        ALL_OF_TYPE_LOOP,
        "            if (object.eContainer() == null) collectTreePaths(object, \"\", labelFeature, childrenFeature, paths);",
        "        }",
        "        return paths;",
        "    }",
        "",
        "    private void collectTreePaths(EObject object, String prefix, String labelFeature, String childrenFeature, List<String> paths) {",
        "        String current = prefix + \"/\" + stringValue(pathValue(object, labelFeature));",
        "        paths.add(current);",
        "        for (Object child : pathValuesFrom(object, childrenFeature)) {",
        "            if (child instanceof EObject) collectTreePaths((EObject) child, current, labelFeature, childrenFeature, paths);",
        "        }",
        "    }",
        "",
        "    private List<String> signaturesOf(List<EObject> roots, String typeName, String[] features) {",
        "        List<String> signatures = new ArrayList<>();",
        "        for (EObject object : allOfType(roots, typeName)) signatures.add(signatureOf(object, features));",
        "        return signatures;",
        "    }",
        "",
        "    private void assertCollectionSize(List<EObject> roots, String typeName, String[] features, String expectedSignature, String path, int expectedSize, String message) {",
        "        boolean matched = false;",
        ALL_OF_TYPE_LOOP,
        "            if (expectedSignature.equals(signatureOf(object, features))) {",
        "                matched = true;",
        "                assertEquals(expectedSize, pathValuesFrom(object, path).size(), message);",
        "            }",
        "        }",
        "        assertTrue(matched, message + \" missing object \" + expectedSignature);",
        "    }",
        "",
        "    private String signatureOf(EObject object, String[] features) {",
        "        List<String> parts = new ArrayList<>();",
        "        for (String feature : features) parts.add(feature + \"=\" + stringValue(pathValue(object, feature)));",
        "        return String.join(\"|\", parts);",
        "    }",
        "",
        "    private Object pathValue(Object object, String path) {",
        "        Object current = object;",
        "        for (String part : path.split(\"\\\\.\")) {",
        "            current = featureValue(current, part);",
        "            if (current == null) return null;",
        "        }",
        "        return current;",
        "    }",
        "",
        "    private List<Object> pathValuesFrom(Object object, String path) {",
        "        List<Object> values = new ArrayList<>();",
        "        if (object == null) return values;",
        "        if (path == null || path.isEmpty()) { addFlattened(values, object); return values; }",
        "        int dot = path.indexOf('.');",
        "        String first = dot >= 0 ? path.substring(0, dot) : path;",
        "        String rest = dot >= 0 ? path.substring(dot + 1) : \"\";",
        "        List<Object> current = new ArrayList<>();",
        "        addFlattened(current, object);",
        "        for (Object value : current) {",
        "            Object next = featureValue(value, first);",
        "            if (rest.isEmpty()) addFlattened(values, next);",
        "            else values.addAll(pathValuesFrom(next, rest));",
        "        }",
        "        return values;",
        "    }",
        "",
        "    private Object featureValue(Object object, String featureName) {",
        "        if (!(object instanceof EObject)) return null;",
        "        EObject eObject = (EObject) object;",
        "        EStructuralFeature feature = eObject.eClass().getEStructuralFeature(featureName);",
        "        return feature == null ? null : eObject.eGet(feature);",
        "    }",
        "",
        "    private void addFlattened(List<Object> values, Object value) {",
        "        if (value instanceof Collection<?>) values.addAll((Collection<?>) value);",
        "        else if (value != null) values.add(value);",
        "    }",
        "",
        "    private String stringValue(Object value) {",
        "        if (value == null) return \"null\";",
        "        if (value instanceof EObject) {",
        "            EObject object = (EObject) value;",
        "            for (String candidate : new String[] {\"name\", \"label\", \"id\", \"value\"}) {",
        "                EStructuralFeature feature = object.eClass().getEStructuralFeature(candidate);",
        "                if (feature != null && object.eGet(feature) != null) return String.valueOf(object.eGet(feature));",
        "            }",
        "        }",
        "        return String.valueOf(value);",
        "    }",
        "",
        "    private <T> List<T> list(T... values) { return new ArrayList<>(List.of(values)); }",
        "",
        "    private Map<String, Integer> counts(List<String> values) {",
        "        Map<String, Integer> counts = new LinkedHashMap<>();",
        "        for (String value : values) counts.merge(value, 1, Integer::sum);",
        "        return counts;",
        "    }",
        "",
        "    private void assertContainsCounts(List<String> expected, List<String> actual, String message) {",
        "        Map<String, Integer> remaining = counts(actual);",
        "        for (Map.Entry<String, Integer> entry : counts(expected).entrySet()) {",
        "            assertTrue(remaining.getOrDefault(entry.getKey(), 0) >= entry.getValue(), message + \" missing \" + entry.getKey());",
        "        }",
        "    }",
    ]
