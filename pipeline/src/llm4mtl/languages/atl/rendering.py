"""Deterministic ATL/JUnit renderer for canonical semantic cases."""

from __future__ import annotations

from typing import Any

from llm4mtl.languages.java_assertions import (
    helpers as assertion_helpers,
    imports as assertion_imports,
    render_assertions,
)
from llm4mtl.languages.java_resources import java_lines
from llm4mtl.semantic_tests.codegen.java_rendering import (
    escape_java,
    rendered_method_name,
)
from llm4mtl.semantic_tests.semantic_spec import effective_models
from llm4mtl.semantic_tests.suites.generated_models import generated_model_resource
from llm4mtl.task_contracts.models import METAMODEL_FILE_SUFFIX


def render_atl_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    """Render the JUnit class that runs every test case of ``spec`` with ATL."""
    methods = [_render_method(spec, test, task) for test in spec["tests"]]
    return "\n".join(
        [
            "package org.example.generated;",
            "",
            *assertion_imports(),
            *java_lines(__package__, "imports.java.txt"),
            f"public class {class_name} {{",
            *java_lines(__package__, "register_factories.java.txt"),
            *methods,
            *java_lines(__package__, "helpers.java.txt"),
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
    source, target = _source_and_target(spec, test)
    execution = _render_execution(spec, task, source, target)
    method_name = rendered_method_name(test)
    model_variables = {
        str(source["name"]): "sourceRoots",
        str(target["name"]): "targetRoots",
    }
    snapshot = f"{escape_java(method_name)}/{escape_java(str(target['name']))}.xmi"
    return "\n".join(
        [
            "    @Test",
            f"    void {method_name}() throws Exception {{",
            *execution,
            f'        writeSnapshot("{snapshot}", targetRoots);',
            *render_assertions(test["assertions"], model_variables),
            "    }",
            "",
        ]
    )


def _source_and_target(
    spec: dict[str, Any], test: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """The one source and one target model an ATL test case must have."""
    models = effective_models(spec, test)
    sources = [model for model in models if model.get("role") == "source"]
    targets = [model for model in models if model.get("role") == "target"]
    if len(sources) != 1 or len(targets) != 1:
        raise ValueError(
            f"ATL scenario {test.get('name')!r} needs exactly one source and "
            "target model"
        )
    return sources[0], targets[0]


def _render_execution(
    spec: dict[str, Any],
    task: str,
    source: dict[str, Any],
    target: dict[str, Any],
) -> list[str]:
    """Load the source model, run the transformation, and keep the target roots."""
    source_path = escape_java(generated_model_resource(task, str(source["path"])))
    source_metamodel = escape_java(_metamodel_name(source))
    target_metamodel = escape_java(_metamodel_name(target))
    transformation = escape_java(str(spec["transformation"]).split("/")[-1])
    return [
        f'        Resource source = loadModel("{source_path}", '
        f'"{source_metamodel}", "{escape_java(_metamodel_uri(source))}");',
        "        List<EObject> sourceRoots = new ArrayList<>(source.getContents());",
        f'        List<EObject> targetRoots = executeAtl("{transformation}", source, '
        f'"{source_metamodel}", "{target_metamodel}", '
        f'"{escape_java(_metamodel_alias(source))}", '
        f'"{escape_java(_metamodel_alias(target))}", '
        f'"{escape_java(_metamodel_uri(target))}");',
    ]


def _runtime_name(model: dict[str, Any]) -> str:
    return str(model.get("runtimeName") or model["name"])


def _metamodel_alias(model: dict[str, Any]) -> str:
    return str(
        model.get("metamodelAlias")
        or model.get("metamodelNsPrefix")
        or _runtime_name(model)
    )


def _metamodel_uri(model: dict[str, Any]) -> str:
    """The nsURI the harness must resolve this model against.

    Some ATL ``.ecore`` files hold two root EPackages (an extra
    ``PrimitiveTypes`` first, the real metamodel second). The harness picks the
    package by this nsURI, not by position.
    """
    return str(model.get("metamodelUri") or "")


def _metamodel_name(model: dict[str, Any]) -> str:
    """The .ecore the harness loads this model against.

    The task contract names the file for every benchmark task. A custom task
    has no contract, so the model's runtime name is used instead of failing.
    """
    path = model.get("metamodelFile")
    if not path:
        return f"{_runtime_name(model)}{METAMODEL_FILE_SUFFIX}"
    return str(path).replace("\\", "/").split("/")[-1]
