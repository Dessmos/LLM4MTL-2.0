"""Java source path and class-name helpers for injected generated tests."""

from __future__ import annotations

import re
from pathlib import Path


def java_destination(test_project_dir: Path, fqcn: str) -> Path:
    parts = fqcn.split(".")
    class_name = parts[-1] + ".java"
    package_parts = parts[:-1]
    return test_project_dir / "src" / "test" / "java" / Path(*package_parts) / class_name


def infer_fqcn(java_path: Path) -> str:
    content = java_path.read_text(encoding="utf-8")
    package_match = re.search(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", content, re.MULTILINE)
    class_match = re.search(
        r"\b(?:public\s+)?(?:class|interface|enum)\s+([A-Za-z_]\w*)\b",
        content,
    )
    if not class_match:
        raise SystemExit(f"Cannot infer Java class name from {java_path}")
    class_name = class_match.group(1)
    if package_match:
        return f"{package_match.group(1)}.{class_name}"
    return class_name


def slug(value: str) -> str:
    slugged = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slugged or "task"
