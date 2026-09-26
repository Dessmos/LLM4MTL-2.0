"""Low-level Java-emitter string helpers (escaping, literals, identifiers).

Some rules are used twice. The renderers use them to write the harness, and
diagnosis runs them again over the recorded semantic cases to find which case or
assertion a Surefire entry came from. They live here so neither side keeps its
own copy: a difference would fail no test and just stop matching real failures.
"""

from __future__ import annotations

import re
from typing import Any, Mapping


def java_string_list(values: list[str]) -> str:
    """Render strings as the Java list expression used by the harness."""
    escaped = ", ".join(f'"{escape_java(value)}"' for value in values)
    return f"list({escaped})" if values else "new ArrayList<>()"


def java_string_array(values: list[str]) -> str:
    """Render strings as a Java array expression."""
    escaped = ", ".join(f'"{escape_java(value)}"' for value in values)
    return f"new String[] {{{escaped}}}"


def java_bool(value: Any) -> str:
    """Render Python truthiness as a Java boolean literal."""
    return "true" if bool(value) else "false"


def safe_temp_prefix(value: str) -> str:
    """Return a prefix accepted by ``File.createTempFile``."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", value)
    return cleaned if len(cleaned) >= 3 else f"{cleaned}_model"


def sanitize_class_name(value: str, task: str) -> str:
    """Return a deterministic valid Java class name.

    ``value`` may be a file name or a qualified name; only the simple class
    name is kept. When ``value`` holds no usable name, the result is
    ``Generated<Task>SemanticTest``, or ``GeneratedSemanticTest`` when ``task``
    holds none either.
    """
    class_name = _simple_class_name(value)
    if class_name:
        return class_name
    return f"Generated{_simple_class_name(task)}SemanticTest"


def _simple_class_name(value: str) -> str:
    """The last dotted part of ``value`` as a Java identifier, or ``""``."""
    simple_name = value.removesuffix(".java").split(".")[-1]
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", simple_name)
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned[0]):
        return ""
    return cleaned


def sanitize_method_name(value: str) -> str:
    """Return a deterministic lower-camel-case Java method name."""
    parts = re.split(r"[^A-Za-z0-9]+", value)
    words = [part for part in parts if part]
    if not words:
        return "generatedSemanticCase"
    first, *rest = words
    method = (
        first[:1].lower()
        + first[1:]
        + "".join(word[:1].upper() + word[1:] for word in rest)
    )
    if not re.match(r"[A-Za-z_]", method[0]):
        method = f"case{method}"
    return method


def rendered_method_name(test_case: Mapping[str, Any]) -> str:
    """The JUnit method name of a semantic case.

    Every renderer names the method after the case ``name``, never its ``id``.
    A case without a name was never rendered, so it gets ``""``, which matches
    no method.
    """
    name = test_case.get("name")
    return "" if name is None else sanitize_method_name(str(name))


def assertion_message(assertion: Mapping[str, Any]) -> str:
    """The message the harness prints when ``assertion`` fails.

    Used twice: the renderer writes it into the generated assertion, and
    diagnosis matches it against the message Surefire recorded to find the
    assertion that failed. An assertion's own ``message`` wins whenever it is
    set, whatever its type, because the renderer writes that into the Java
    literal.

    Returns ``""`` when there is no message and no fields to build the default
    from. The renderer never hits that case. For diagnosis it means the
    assertion cannot be matched, so no failure is attributed to it.
    """
    explicit = assertion.get("message")
    if explicit:
        return str(explicit)
    if not all(field in assertion for field in ("kind", "model", "type")):
        return ""
    return (
        f"{assertion['kind']} assertion for "
        f"{assertion['model']}::{assertion['type']}"
    )


def escape_java(value: str) -> str:
    """Escape backslashes and quotes for a Java string literal body."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def java_value(value: Any) -> str:
    """Render an ``expected`` value the way the harness renders what it observes.

    The harness turns model values into strings through Java: a boolean reads
    ``true``/``false`` and an unset value reads ``null``. Python's ``str`` would
    write ``True`` and ``None``, which never match what the harness sees.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def object_signatures(raw_objects: list[Any], features: list[str]) -> list[str]:
    signatures = []
    for raw_object in raw_objects:
        if not isinstance(raw_object, dict):
            # Parsing already rejects such a specification; reaching this is a
            # renderer called on unvalidated input, not a generated-test defect.
            raise ValueError("objects assertion expected entries must be objects")
        parts = [
            f"{feature}={java_value(raw_object.get(feature))}" for feature in features
        ]
        signatures.append("|".join(parts))
    return signatures
