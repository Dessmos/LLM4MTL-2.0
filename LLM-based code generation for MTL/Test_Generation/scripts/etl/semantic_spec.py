"""Shared semantic-case constants and spec accessors.

Neutral leaf module: imports nothing from `etl.extraction` or `etl.codegen`, so
both the semantic_cases pipeline and the codegen emitter can depend on it
without forming an import cycle. Do not add heavy imports here.
"""

from __future__ import annotations

from typing import Any


SEMANTIC_CASES_FILE = "semantic_cases.json"
CONTRACT_VIOLATIONS_FILE = "contract_violations.json"


def effective_models(spec: dict[str, Any], test: dict[str, Any]) -> list[dict[str, Any]]:
    models = test.get("models", spec.get("models", []))
    return [dict(model) for model in models]


def default_transformation(task: str) -> str:
    return f"transformations/{task}.etl"
