"""Low-level Java-emitter string helpers (escaping, literals, identifiers).

Some of these rules are read in both directions. The emitter uses them to write
the harness; diagnosis runs them forwards again over the recorded semantic
cases to work out which case or assertion a Surefire entry came from. Those
rules live here so neither side can restate them: a divergence would fail
nothing and simply stop matching real failures.
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
    """Return a deterministic valid Java class name."""
    value = value.split(".")[-1]
    value = value.removesuffix(".java")
    cleaned = re.sub(r"[^A-Za-z0-9_]", "", value)
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned[0]):
        return f"Generated{sanitize_class_name(task, 'ETL')}SemanticTest"
    return cleaned


def sanitize_method_name(value: str) -> str:
    """Return a deterministic lower-camel-case Java method name."""
    parts = re.split(r"[^A-Za-z0-9]+", value)
    words = [part for part in parts if part]
    if not words:
        return "generatedSemanticCase"
    first, *rest = words
    method = first[:1].lower() + first[1:] + "".join(
        word[:1].upper() + word[1:] for word in rest
    )
    if not re.match(r"[A-Za-z_]", method[0]):
        method = f"case{method}"
    return method


def assertion_message(assertion: Mapping[str, Any]) -> str:
    """The message the harness prints when ``assertion`` fails.

    Read in both directions: the renderer embeds it in the generated assertion,
    and diagnosis matches it against the message Surefire recorded to attribute
    a failure to the assertion that lost. The renderer is the authority — an
    assertion's own ``message`` is used whenever it has one, whatever its type,
    because that is what the renderer stringifies into the Java literal.

    Returns ``""`` when there is no message and no fields to build the default
    from. The renderer cannot reach that case; it resolves those fields before
    it asks for a message. For the reader it means this assertion cannot be
    matched, which is a refusal to attribute rather than a guess.
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
