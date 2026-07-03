"""JUnit smoke-test helpers for technical validation."""

from __future__ import annotations

import re
from pathlib import Path


JUNIT_TEST_ANNOTATION = re.compile(
    r"^\s*@(?:org\.junit\.jupiter\.api\.)?Test\b",
    re.MULTILINE,
)


def junit_test_method_counts(java_paths: list[Path]) -> dict[Path, int]:
    return {
        java_path: len(JUNIT_TEST_ANNOTATION.findall(java_path.read_text(encoding="utf-8")))
        for java_path in java_paths
    }


def surefire_test_selector(class_names: list[str]) -> str:
    return ",".join(class_names)
