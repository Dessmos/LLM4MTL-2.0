"""Loading of deterministic task model contracts from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm4mtl.conventions import ETL_CONFIG, LanguageConfig, default_task_contracts_root
from llm4mtl.task_contracts.models import EMF_KIND, ModelContract, TaskContract


def load_task_contract(
    task: str,
    contracts_root: Path | None = None,
    config: LanguageConfig = ETL_CONFIG,
) -> TaskContract | None:
    """Return the contract for ``task`` or ``None`` when no contract exists.

    A missing contract is not an error here. Language adapters still reject a
    suite whose benchmark task has no contract.
    """
    root = contracts_root or default_task_contracts_root(config)
    path = Path(root) / f"{task}.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    return contract_from_mapping(data, task)


def contract_from_mapping(
    data: dict[str, Any], task: str | None = None
) -> TaskContract:
    """Build a ``TaskContract`` from an already-parsed contract mapping."""
    models = tuple(
        _model_from_dict(raw) for raw in data.get("models", []) if isinstance(raw, dict)
    )
    resolved_task = str(data.get("task") or task or "")
    return TaskContract(
        task=resolved_task,
        # No default: guessing ".etl" would put an ETL assumption into ATL,
        # QVT-O, or Reactions runs.
        transformation=str(data.get("transformation") or ""),
        models=models,
    )


def _model_from_dict(raw: dict[str, Any]) -> ModelContract:
    return ModelContract(
        runtime_name=str(raw.get("runtimeName") or ""),
        roles=tuple(str(role) for role in raw.get("roles", [])),
        kind=str(raw.get("kind") or EMF_KIND),
        metamodel_uri=_optional_text(raw, "metamodelUri"),
        metamodel_ns_prefix=_optional_text(raw, "metamodelNsPrefix"),
        metamodel_alias=_optional_text(raw, "metamodelAlias"),
        metamodel_file=_optional_text(raw, "metamodelFile"),
        types_used_in_transformation=_types_used_in_transformation(raw),
        available_types=tuple(
            str(type_name) for type_name in raw.get("availableTypes", [])
        ),
    )


def _optional_text(raw: dict[str, Any], key: str) -> str | None:
    """``raw[key]`` as text, or ``None`` when it is absent or empty."""
    return str(raw[key]) if raw.get(key) else None


def _types_used_in_transformation(raw: dict[str, Any]) -> tuple[str, ...]:
    # Also accept the older snake_case key, which schemas/contract.schema.json
    # still allows.
    types_used = (
        raw.get("typesUsedInTransformation")
        or raw.get("types_used_in_transformation")
        or []
    )
    return tuple(str(type_name) for type_name in types_used)
