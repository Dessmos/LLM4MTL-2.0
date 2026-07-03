"""Generate deterministic Java tests from semantic-case artifacts."""

from __future__ import annotations

import json
import re
from typing import Any

from etl.suites.java import slug


SEMANTIC_CASES_FILE = "semantic_cases.json"


def can_generate_java_from_semantic_cases(target_task: str) -> bool:
    return target_task == "Tree2Graph"


def augment_with_generated_java(target_task: str, extracted: dict[str, str]) -> dict[str, str]:
    cases_json = extracted.get(SEMANTIC_CASES_FILE)
    if not cases_json:
        return extracted

    if not can_generate_java_from_semantic_cases(target_task):
        return extracted

    spec = parse_semantic_cases(cases_json)
    java_file = spec.get("testClass") or f"Generated{target_task}SemanticTest"
    java_file = sanitize_class_name(str(java_file))
    generated = dict(extracted)

    # Plan B: semantic cases are the source of truth. Ignore any Java emitted by
    # the LLM and replace it with the deterministic harness.
    for path in list(generated):
        if path.endswith(".java"):
            del generated[path]
    generated[f"{java_file}.java"] = render_tree2graph_test(java_file, spec, target_task)
    return generated


def parse_semantic_cases(raw_json: str) -> dict[str, Any]:
    try:
        spec = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid {SEMANTIC_CASES_FILE}: {exc}") from exc

    tests = spec.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SystemExit(f"{SEMANTIC_CASES_FILE} must contain a non-empty tests array")

    for index, test in enumerate(tests, start=1):
        if not isinstance(test, dict):
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} must be an object")
        if not test.get("name"):
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} is missing name")
        if not test.get("inputModel"):
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} is missing inputModel")
        if "expectedNodes" not in test:
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} is missing expectedNodes")
        if "expectedEdges" not in test:
            raise SystemExit(f"{SEMANTIC_CASES_FILE} test #{index} is missing expectedEdges")
    return spec


def render_tree2graph_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    methods = []
    for test in spec["tests"]:
        methods.append(render_tree2graph_method(test, task))

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
            "import org.eclipse.epsilon.emc.emf.EmfModel;",
            "import org.eclipse.epsilon.examples.etl.EtlTestBase;",
            "import org.junit.jupiter.api.BeforeEach;",
            "import org.junit.jupiter.api.Test;",
            "",
            f"public class {class_name} extends EtlTestBase {{",
            '    private static final String ETL = "transformations/Tree2Graph.etl";',
            "",
            "    @BeforeEach",
            "    public void setUp() throws Exception {",
            '        registerMetamodel("metamodels/Tree.ecore");',
            '        registerMetamodel("metamodels/Graph.ecore");',
            "    }",
            "",
            *methods,
            "    private RunResult runTransformation(String inputModel) throws Exception {",
            '        EmfModel source = createEmfModel("Tree", inputModel, "Tree", true, false);',
            '        File targetFile = File.createTempFile("tree2graph_generated_", ".model");',
            "        targetFile.deleteOnExit();",
            '        EmfModel target = createEmfModelFromFile("Graph", targetFile.getAbsolutePath(), "Graph", false, true);',
            "        runEtl(ETL, source, target);",
            "        return new RunResult(source, target);",
            "    }",
            "",
            "    private List<String> namesOf(EmfModel model, String typeName, String featureName) throws Exception {",
            "        List<String> names = new ArrayList<>();",
            "        for (EObject object : allOfType(model, typeName)) {",
            "            names.add(stringFeature(object, featureName));",
            "        }",
            "        return names;",
            "    }",
            "",
            "    private List<String> edgePairs(EmfModel model) throws Exception {",
            "        List<String> pairs = new ArrayList<>();",
            '        for (EObject edge : allOfType(model, "Edge")) {',
            '            EObject source = reference(edge, "source");',
            '            EObject target = reference(edge, "target");',
            "            assertNotNull(source, \"Edge.source must be set\");",
            "            assertNotNull(target, \"Edge.target must be set\");",
            '            pairs.add(stringFeature(source, "name") + "->" + stringFeature(target, "name"));',
            "        }",
            "        return pairs;",
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
            "    private Collection<EObject> allOfType(EmfModel model, String typeName) throws Exception {",
            "        Collection<?> values = model.getAllOfType(typeName);",
            "        Collection<EObject> result = new ArrayList<>();",
            "        for (Object value : values) {",
            "            result.add((EObject) value);",
            "        }",
            "        return result;",
            "    }",
            "",
            "    private String stringFeature(EObject object, String featureName) {",
            "        Object value = object.eGet(object.eClass().getEStructuralFeature(featureName));",
            "        return value == null ? null : String.valueOf(value);",
            "    }",
            "",
            "    private EObject reference(EObject object, String featureName) {",
            "        return (EObject) object.eGet(object.eClass().getEStructuralFeature(featureName));",
            "    }",
            "",
            "    private static final class RunResult {",
            "        final EmfModel source;",
            "        final EmfModel target;",
            "",
            "        RunResult(EmfModel source, EmfModel target) {",
            "            this.source = source;",
            "            this.target = target;",
            "        }",
            "    }",
            "}",
            "",
        ]
    )


def render_tree2graph_method(test: dict[str, Any], task: str) -> str:
    method_name = sanitize_method_name(str(test["name"]))
    input_model = resource_path(str(test["inputModel"]), task)
    expected_nodes = expected_node_names(test["expectedNodes"])
    expected_edges = expected_edge_pairs(test["expectedEdges"])

    return "\n".join(
        [
            "    @Test",
            f"    public void {method_name}() throws Exception {{",
            f'        RunResult run = runTransformation("{escape_java(input_model)}");',
            f"        List<String> expectedNodes = {java_string_list(expected_nodes)};",
            f"        List<String> expectedEdges = {java_string_list(expected_edges)};",
            '        assertEquals(counts(expectedNodes), counts(namesOf(run.target, "Node", "name")), "Node name multiplicities must match expected Tree labels");',
            '        assertEquals(counts(expectedEdges), counts(edgePairs(run.target)), "Edge multiplicities must match expected source->target Node names");',
            '        assertEquals(expectedNodes.size(), allOfType(run.target, "Node").size(), "No superfluous or missing Nodes");',
            '        assertEquals(expectedEdges.size(), allOfType(run.target, "Edge").size(), "No superfluous or missing Edges");',
            "    }",
            "",
        ]
    )


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
    return f"Arrays.asList({escaped})" if values else "new ArrayList<>()"


def resource_path(input_model: str, task: str) -> str:
    path = input_model.replace("\\", "/")
    filename = path.split("/")[-1]
    return f"generated-models/{slug(task)}/{filename}"


def sanitize_class_name(value: str) -> str:
    value = value.removesuffix(".java")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value)
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned[0]):
        return "GeneratedTree2GraphSemanticTest"
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
