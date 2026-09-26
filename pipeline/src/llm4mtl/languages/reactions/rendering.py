"""Deterministic Reactions/Vitruv JUnit renderer.

The generated Java is infrastructure only. Model changes come from a fixed,
declarative list in ``semantic_cases.json`` and are turned into reflective EMF
calls here; the LLM never writes executable change code.
"""

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

# The name of the view variable inside every rendered ``modify`` lambda.
VIEW = "view"

# Declarative change kinds that call one harness helper on a found element.
FEATURE_OPERATIONS = {
    "set_feature": "setFeature",
    "add_to_collection": "addToCollection",
    "remove_from_collection": "removeFromCollection",
    "move": "moveInto",
}


def _specification(task: str) -> str:
    return f"{task}ChangePropagationSpecification"


def render_reactions_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    """Render the JUnit class that runs every test case of ``spec`` in Vitruv."""
    # Always one specification: the adapter merges prerequisites into this
    # task's reactions file (see ``ReactionsAdapter._with_prerequisites``).
    reaction_name = task[:1].lower() + task[1:]
    specification = _specification(task)
    return "\n".join(
        [
            "package tools.vitruv.methodologisttemplate.generated;",
            "",
            *assertion_imports(),
            *java_lines(__package__, "imports.java.txt"),
            f"import mir.reactions.{reaction_name}.{specification};",
            "",
            f"public class {class_name} {{",
            *java_lines(__package__, "register_factories.java.txt"),
            *[_render_method(test, task, specification) for test in spec["tests"]],
            *java_lines(__package__, "helpers.java.txt"),
            *assertion_helpers(),
            "}",
            "",
        ]
    )


def _render_method(
    test: dict[str, Any],
    task: str,
    specification: str,
) -> str:
    models = effective_models({}, test)
    slot_uris = {str(model["name"]): str(model["metamodelUri"]) for model in models}
    method_name = rendered_method_name(test)
    lines = [
        "    @Test",
        f"    void {method_name}(@TempDir Path tempDir) throws Exception {{",
        *_render_virtual_model(test, specification),
        *_render_initial_models(models, task),
    ]
    for index, change in enumerate(test.get("changes", [])):
        lines.extend(_render_change(change, slot_uris, index))
    lines.extend(_render_model_roots(models, method_name))
    variables = {
        str(model["name"]): _roots_variable(index)
        for index, model in enumerate(models)
    }
    lines.extend(render_assertions(test["assertions"], variables))
    lines.extend(["    }", ""])
    return "\n".join(lines)


def _render_virtual_model(test: dict[str, Any], specification: str) -> list[str]:
    """Create the virtual model with the user answers this test case gives.

    A routine may ask the user which of several targets to create. The test
    says which option it means; without an answer the interaction throws and
    no assertion is ever reached.
    """
    selections = test.get("userSelections") or []
    return [
        "        TestUserInteraction interaction = new TestUserInteraction();",
        *[
            f"        interaction.addNextSingleSelection({int(selection)});"
            for selection in selections
        ],
        "        InternalVirtualModel vsum = "
        f"createVirtualModel(tempDir, interaction, new {specification}());",
    ]


def _render_initial_models(models: list[dict[str, Any]], task: str) -> list[str]:
    """Register every model file the test case starts from."""
    lines = []
    for model in models:
        path = model.get("path")
        if not path:
            continue
        resource = escape_java(generated_model_resource(task, str(path)))
        lines.append(f'        registerInitialModel(vsum, tempDir, "{resource}");')
    return lines


def _render_model_roots(models: list[dict[str, Any]], method_name: str) -> list[str]:
    """Read each model's roots after the changes and write its snapshot."""
    lines = []
    for index, model in enumerate(models):
        variable = _roots_variable(index)
        uri = escape_java(str(model["metamodelUri"]))
        snapshot = f"{escape_java(method_name)}/{escape_java(str(model['name']))}.xmi"
        lines.append(f'        List<EObject> {variable} = modelRoots(vsum, "{uri}");')
        lines.append(f'        writeSnapshot("{snapshot}", {variable});')
    return lines


def _roots_variable(index: int) -> str:
    return f"model{index}Roots"


def _render_change(
    change: dict[str, Any],
    slot_uris: dict[str, str],
    index: int,
) -> list[str]:
    target = change["target"]
    slot = str(target.get("slot", target.get("model")))
    uri = slot_uris[slot]
    return [
        f'        modify(vsum, "{escape_java(uri)}", {VIEW} -> {{',
        *_render_change_body(change, uri, slot_uris, index),
        "        });",
    ]


def _render_change_body(
    change: dict[str, Any],
    uri: str,
    slot_uris: dict[str, str],
    index: int,
) -> list[str]:
    """The statements inside the ``modify`` lambda; ``uri`` is the changed slot's."""
    target = change["target"]
    kind = str(change["kind"])
    if kind == "create":
        return _render_create(change, uri, slot_uris, index)
    if kind == "delete":
        return [f"            EcoreUtil.delete({_find_expression(uri, target)}, true);"]
    operation = FEATURE_OPERATIONS.get(kind)
    if operation is None:
        raise ValueError(f"unsupported Reactions change kind: {kind}")
    feature = escape_java(str(change.get("feature") or ""))
    target_expression = _find_expression(uri, target)
    value = _java_value(change.get("value"), slot_uris, uri)
    return [f'            {operation}({target_expression}, "{feature}", {value});']


def _render_create(
    change: dict[str, Any],
    uri: str,
    slot_uris: dict[str, str],
    index: int,
) -> list[str]:
    """Create an element and add it to the target's feature, or as a new root."""
    created = f"created{index}"
    lines = [
        f"            EObject {created} = "
        f"{_java_value(change.get('value'), slot_uris, uri)};"
    ]
    feature = escape_java(str(change.get("feature") or ""))
    if feature:
        target_expression = _find_expression(uri, change["target"])
        lines.append(
            f'            addToCollection({target_expression}, "{feature}", {created});'
        )
        return lines
    lines.append(
        f"            {VIEW}.registerRoot({created}, "
        "URI.createFileURI(tempDir.resolve("
        f'"created-{index}.xmi").toString()));'
    )
    return lines


def _java_value(
    value: Any,
    slot_uris: dict[str, str],
    default_uri: str,
) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Boolean.TRUE" if value else "Boolean.FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{escape_java(value)}"'
    if not isinstance(value, dict):
        raise ValueError(f"unsupported declarative change value: {value!r}")
    return _java_object_value(value, slot_uris, default_uri)


def _java_object_value(
    value: dict[str, Any],
    slot_uris: dict[str, str],
    default_uri: str,
) -> str:
    if value.get("slot") or value.get("model"):
        slot = str(value.get("slot", value.get("model")))
        return _find_expression(slot_uris[slot], value)
    type_name = value.get("type")
    if not type_name:
        raise ValueError("a created element needs a type")
    features = value.get("features") if isinstance(value.get("features"), dict) else {}
    return (
        f'createObject("{escape_java(default_uri)}", "{escape_java(str(type_name))}", '
        f"{_java_map(features)})"
    )


def _find_expression(uri: str, reference: dict[str, Any]) -> str:
    """A ``find`` call for the element that ``reference`` describes."""
    where = reference.get("where") if isinstance(reference.get("where"), dict) else {}
    return (
        f'find({VIEW}, "{escape_java(uri)}", '
        f'"{escape_java(str(reference["type"]))}", {_java_map(where)})'
    )


def _java_map(values: dict[str, Any]) -> str:
    if not values:
        return "map()"
    entries: list[str] = []
    for key, value in values.items():
        entries.append(f'"{escape_java(str(key))}"')
        entries.append(_java_literal(value))
    return f"map({', '.join(entries)})"


def _java_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Boolean.TRUE" if value else "Boolean.FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{escape_java(str(value))}"'
