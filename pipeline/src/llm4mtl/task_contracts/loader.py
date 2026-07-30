"""Loading of deterministic task model contracts from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.conventions import ETL_CONFIG, LanguageConfig, default_task_contracts_root
from llm4mtl.task_contracts.models import ModelContract, TaskContract


def load_task_contract(
    task: str,
    contracts_root: Path | None = None,
    config: LanguageConfig = ETL_CONFIG,
) -> TaskContract | None:
    """Return the contract for ``task`` or ``None`` when no contract exists.

    A missing contract is not an error at this low-level loader. Production
    adapters still fail artifact validation when a required benchmark contract
    is absent.
    """
    root = contracts_root or default_task_contracts_root(config)
    path = Path(root) / f"{task}.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return contract_from_mapping(data, task)


def contract_from_mapping(data: dict[str, Any], task: str | None = None) -> TaskContract:
    """Build a ``TaskContract`` from an already-parsed contract mapping."""
    models = tuple(
        _model_from_dict(raw)
        for raw in data.get("models", [])
        if isinstance(raw, dict)
    )
    resolved_task = str(data.get("task") or task or "")
    return TaskContract(
        task=resolved_task,
        transformation=str(data.get("transformation") or f"{resolved_task}.etl"),
        models=models,
    )


def _model_from_dict(raw: dict[str, Any]) -> ModelContract:
    return ModelContract(
        runtime_name=str(raw.get("runtimeName") or ""),
        roles=tuple(str(role) for role in raw.get("roles", [])),
        kind=str(raw.get("kind") or "emf"),
        metamodel_uri=str(raw["metamodelUri"]) if raw.get("metamodelUri") else None,
        metamodel_ns_prefix=str(raw["metamodelNsPrefix"]) if raw.get("metamodelNsPrefix") else None,
        metamodel_alias=str(raw["metamodelAlias"]) if raw.get("metamodelAlias") else None,
        metamodel_file=str(raw["metamodelFile"]) if raw.get("metamodelFile") else None,
        types_used_in_transformation=tuple(
            str(type_name)
            for type_name in (
                raw.get("typesUsedInTransformation")
                or raw.get("typesUsedInEtL")
                or raw.get("types_used_in_transformation")
                or raw.get("types_used_in_etl")
                or []
            )
        ),
        available_types=tuple(str(type_name) for type_name in raw.get("availableTypes", [])),
    )
