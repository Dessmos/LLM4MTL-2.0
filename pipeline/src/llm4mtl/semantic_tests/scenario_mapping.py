"""Express a generated ETL suite in the shared scenario contract.

Every generated suite must be representable in :mod:`llm4mtl.domain` before it
is allowed to execute. This is what keeps the shared contract honest: if a suite
the ETL path accepts cannot be expressed, the contract is wrong and says so
loudly, rather than the contract quietly describing only the parts of ETL that
happened to fit.

The engine-specific parts of a slot (Epsilon model kind, load/store flags, the
runtime model name) stay out of the shared types and remain in the spec the ETL
renderer consumes. What the shared contract carries is what every language has:
named model slots with roles and metamodels, and expectations over them.
"""

from __future__ import annotations

from typing import Any

from llm4mtl.domain import (
    Expectation,
    ModelRole,
    ModelSlot,
    ScenarioKind,
    SemanticScenario,
    SemanticSuite,
)
from llm4mtl.semantic_tests.semantic_spec import effective_models

# Assertion vocabulary of the ETL spec -> the shared expectation vocabulary.
EXPECTATION_KINDS = {
    "count": "count",
    "featureValues": "feature_values",
    "pathValues": "path_values",
    "treePaths": "tree_paths",
    "collectionSize": "collection_size",
    "objects": "objects",
    "referencePairs": "reference_pairs",
}


class ScenarioMappingError(ValueError):
    """Raised when a generated suite cannot be expressed in the shared contract."""


def suite_from_spec(spec: dict[str, Any], *, suite_id: str, language: str, task: str) -> SemanticSuite:
    """Build the shared representation of one generated suite."""
    try:
        scenarios = tuple(_scenario(spec, test) for test in spec.get("tests", []))
        return SemanticSuite(
            suite_id=suite_id, language=language, task=task, scenarios=scenarios
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise ScenarioMappingError(
            f"suite cannot be expressed as semantic scenarios: {exc}"
        ) from exc


def _scenario(spec: dict[str, Any], test: dict[str, Any]) -> SemanticScenario:
    models = effective_models(spec, test)
    return SemanticScenario(
        name=str(test["name"]),
        # ETL is a batch model-to-model transformation; change propagation is the
        # Reactions shape and is produced by that adapter, not this one.
        kind=ScenarioKind.BATCH_TRANSFORMATION,
        slots=tuple(_slot(model) for model in models),
        expectations=tuple(_expectation(assertion) for assertion in test.get("assertions", [])),
    )


def _slot(model: dict[str, Any]) -> ModelSlot:
    role = str(model.get("role") or ("source" if model.get("path") else "target"))
    return ModelSlot(
        name=str(model["name"]),
        role=ModelRole.INPUT if role == "source" else ModelRole.OUTPUT,
        metamodel=str(model.get("metamodelUri") or model["name"]),
        artifact=str(model["path"]) if model.get("path") else None,
    )


def _expectation(assertion: dict[str, Any]) -> Expectation:
    kind = str(assertion.get("kind", ""))
    if kind not in EXPECTATION_KINDS:
        raise ValueError(f"unsupported assertion kind '{kind}'")
    payload = {
        key: value
        for key, value in assertion.items()
        if key not in {"kind", "model", "type"}
    }
    return Expectation(
        kind=EXPECTATION_KINDS[kind],
        slot=str(assertion["model"]),
        type_name=str(assertion["type"]),
        payload=payload,
    )
