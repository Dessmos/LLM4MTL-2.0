"""Smoke-test source generation for technical validation."""

from __future__ import annotations

from pathlib import Path

from common.injection import Injection
from etl.technical_validation.java import java_destination
from etl.technical_validation.models import SMOKE_TEST_CLASS, SMOKE_TEST_FQCN, SMOKE_TEST_PACKAGE


def inject_smoke_test(etl_test_dir: Path, class_names: list[str], injection: Injection) -> None:
    destination = java_destination(etl_test_dir, SMOKE_TEST_FQCN)
    injection.write_text(destination, render_smoke_test_source(class_names))


def render_smoke_test_source(class_names: list[str]) -> str:
    lines = [
        f"package {SMOKE_TEST_PACKAGE};",
        "",
        "import static org.junit.jupiter.api.Assertions.assertNotNull;",
        "",
        "import org.junit.jupiter.api.Test;",
        "",
        f"public class {SMOKE_TEST_CLASS} {{",
        "    @Test",
        "    public void generatedTestClassesCanBeLoaded() throws Exception {",
        "        for (String className : new String[] {",
        *java_string_array_entries(class_names, indent="            "),
        "        }) {",
        "            assertNotNull(Class.forName(className));",
        "        }",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


def java_string_array_entries(values: list[str], indent: str) -> list[str]:
    entries = []
    for index, value in enumerate(values):
        comma = "," if index < len(values) - 1 else ""
        entries.append(f'{indent}"{escape_java_string(value)}"{comma}')
    return entries


def escape_java_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
