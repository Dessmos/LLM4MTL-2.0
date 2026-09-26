"""Deterministic reflective EMF assertions for generated Java harnesses."""

from __future__ import annotations

from typing import Any

from llm4mtl.languages.java_resources import java_lines
from llm4mtl.semantic_tests.codegen.java_rendering import (
    assertion_message,
    escape_java,
    java_string_array,
    java_string_list,
    java_value,
    object_signatures,
)


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
            return _render_count_assertion(assertion, model, type_name, message)
        case "featureValues" | "pathValues" | "treePaths":
            return _render_path_collection_assertion(
                assertion, model, type_name, message
            )
        case "collectionSize" | "objects" | "referencePairs":
            return _render_object_collection_assertion(
                assertion, model, type_name, message
            )
        case _:
            raise ValueError(f"unsupported assertion kind: {kind}")


def _render_count_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    expected = int(assertion["expected"])
    actual = f'allOfType({model}, "{type_name}").size()'
    return [f'        assertEquals({expected}, {actual}, "{message}");']


def _render_path_collection_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    kind = str(assertion["kind"])
    expected = java_string_list([java_value(value) for value in assertion["expected"]])
    if kind in {"featureValues", "pathValues"}:
        path_key = "feature" if kind == "featureValues" else "path"
        path = escape_java(str(assertion[path_key]))
        actual = f'pathValues({model}, "{type_name}", "{path}")'
    else:
        label = escape_java(str(assertion.get("labelFeature") or "label"))
        children = escape_java(str(assertion.get("childrenFeature") or "children"))
        actual = f'treePaths({model}, "{type_name}", "{label}", "{children}")'
    return _collection_assertion(expected, actual, assertion, message)


def _render_object_collection_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    match str(assertion["kind"]):
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
    where = assertion.get("where") if isinstance(assertion.get("where"), dict) else {}
    features = [str(feature) for feature in where]
    expected_signature = object_signatures([where], features)[0] if features else ""
    path = escape_java(str(assertion["path"]))
    return [
        f'        assertCollectionSize({model}, "{type_name}", '
        f"{java_string_array(features)}, "
        f'"{escape_java(expected_signature)}", "{path}", '
        f'{int(assertion["expected"])}, "{message}");'
    ]


def _render_objects_assertion(
    assertion: dict[str, Any],
    model: str,
    type_name: str,
    message: str,
) -> list[str]:
    features = [str(feature) for feature in assertion["features"]]
    expected = object_signatures(assertion["expected"], features)
    actual = f'signaturesOf({model}, "{type_name}", ' f"{java_string_array(features)})"
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
        f"{java_value(pair['source'])}->{java_value(pair['target'])}"
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
    """Java imports every shared-assertion harness needs."""
    return java_lines(__package__, "assertion_imports.java.txt")


def helpers() -> list[str]:
    """Java helpers operating on canonical lists of EMF roots.

    Notes on the emitted Java:

    * ``writeSnapshot`` takes ``<test-case>/<model-slot>.xmi``, so each snapshot
      names the case and the slot that produced it. It creates the parent
      folder, which is what lets the case be a folder.
    * ``pathValues`` keeps an unset last value as ``"null"``: a suite must be
      able to say that a created operation has no name.
    """
    return java_lines(__package__, "assertion_helpers.java.txt")
