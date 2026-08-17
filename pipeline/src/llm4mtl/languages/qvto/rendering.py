"""Deterministic QVT-O/JUnit renderer for canonical semantic cases."""

from __future__ import annotations

from typing import Any

from llm4mtl.languages.java_assertions import (
    helpers as assertion_helpers,
    imports as assertion_imports,
    render_assertions,
)
from llm4mtl.semantic_tests.codegen.java_rendering import (
    escape_java,
    sanitize_method_name,
)
from llm4mtl.semantic_tests.semantic_spec import effective_models
from llm4mtl.semantic_tests.suites.java import slug


def render_qvto_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    return "\n".join(
        [
            "package org.eclipse.qvto.tests;",
            "",
            *assertion_imports(),
            "import org.eclipse.m2m.qvt.oml.BasicModelExtent;",
            "import org.junit.jupiter.api.Test;",
            "",
            f"public class {class_name} extends QvtoTestBase {{",
            *[_render_method(spec, test, task) for test in spec["tests"]],
            *assertion_helpers(),
            "}",
            "",
        ]
    )


def _render_method(
    spec: dict[str, Any],
    test: dict[str, Any],
    task: str,
) -> str:
    models = effective_models(spec, test)
    sources = [model for model in models if model.get("role") == "source"]
    targets = [model for model in models if model.get("role") == "target"]
    if len(sources) != 1 or len(targets) not in (1, 2):
        raise ValueError(
            f"QVT-O scenario {test.get('name')!r} needs one source and one or two targets"
        )
    source = sources[0]
    path = str(source["path"]).replace("\\", "/")
    if path.startswith("models/"):
        path = path[len("models/") :]
    resource_path = f"generated-models/{slug(task)}/{path}"
    transformation = str(spec["transformation"]).split("/")[-1]
    variables = {str(source["name"]): "sourceRoots"}
    lines = [
        "    @Test",
        f"    void {sanitize_method_name(str(test['name']))}() throws Exception {{",
        f'        BasicModelExtent input = loadInputModel("{escape_java(resource_path)}");',
        "        List<EObject> sourceRoots = new ArrayList<>(input.getContents());",
    ]
    lines.extend(_render_outputs(targets, transformation, test, variables))
    lines.extend(
        [
            *render_assertions(test["assertions"], variables),
            "    }",
            "",
        ]
    )
    return "\n".join(lines)


def _render_outputs(
    targets: list[dict[str, Any]],
    transformation: str,
    test: dict[str, Any],
    variables: dict[str, str],
) -> list[str]:
    """Render target extents and register their assertion variables."""
    escaped_transformation = escape_java(transformation)
    test_name = escape_java(sanitize_method_name(str(test["name"])))
    if len(targets) == 1:
        target_name = escape_java(str(targets[0]["name"]))
        variables[str(targets[0]["name"])] = "target0Roots"
        return [
            "        BasicModelExtent output = "
            f'executeTransformation("{escaped_transformation}", input);',
            "        List<EObject> target0Roots = new ArrayList<>(output.getContents());",
            f'        writeSnapshot("{test_name}/{target_name}.xmi", target0Roots);',
        ]

    lines = [
        "        BasicModelExtent[] outputs = "
        f'executeTransformation2Outputs("{escaped_transformation}", input);'
    ]
    for index, target in enumerate(targets):
        variable = f"target{index}Roots"
        target_name = escape_java(str(target["name"]))
        variables[str(target["name"])] = variable
        lines.append(
            f"        List<EObject> {variable} = new ArrayList<>(outputs[{index}].getContents());"
        )
        lines.append(
            f'        writeSnapshot("{test_name}/{target_name}.xmi", {variable});'
        )
    return lines
