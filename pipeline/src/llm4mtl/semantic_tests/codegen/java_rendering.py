"""Low-level Java-emitter string helpers (escaping, literals, identifiers)."""

from __future__ import annotations

import re
from typing import Any


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


def escape_java(value: str) -> str:
    """Escape backslashes and quotes for a Java string literal body."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
