"""Typed view over a deterministic task model contract.

A contract maps one language's runtime model names to their EMF metamodel URIs,
namespace prefixes, ``.ecore`` inputs, and available types. It is deterministic
benchmark input and must never be overridden by an LLM guess.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelContract:
    """Deterministic binding for a single runtime model of a task."""

    runtime_name: str
    roles: tuple[str, ...]
    kind: str
    metamodel_uri: str | None
    metamodel_ns_prefix: str | None
    metamodel_alias: str | None
    metamodel_file: str | None
    types_used_in_transformation: tuple[str, ...]
    available_types: tuple[str, ...]

    def has_role(self, role: str) -> bool:
        if role == "inout":
            return "inout" in self.roles
        return role in self.roles or "inout" in self.roles

    @property
    def metamodel_resource(self) -> str | None:
        """Classpath-relative ``.ecore`` path used by the ETL_Test harness."""
        if not self.metamodel_file:
            return None
        return f"metamodels/{Path(self.metamodel_file).name}"


@dataclass(frozen=True)
class TaskContract:
    """Deterministic model contract for one transformation task."""

    task: str
    transformation: str
    models: tuple[ModelContract, ...]

    def models_for_role(self, role: str) -> list[ModelContract]:
        return [model for model in self.models if model.has_role(role)]

    @property
    def identifiers(self) -> set[str]:
        """Lower-cased identifiers that legitimately name this task's metamodels.

        Used to reject ``semantic_cases.json`` that declares metamodels outside
        the contract (a metamodel URI, runtime name, ns prefix, or ``.ecore``
        stem all count as valid ways to refer to a contracted metamodel).
        """
        names: set[str] = set()
        for model in self.models:
            for value in (
                model.metamodel_uri,
                model.runtime_name,
                model.metamodel_ns_prefix,
                model.metamodel_alias,
            ):
                if value:
                    names.add(value.lower())
            if model.metamodel_file:
                names.add(Path(model.metamodel_file).stem.lower())
        return names

    @property
    def emf_metamodel_resources(self) -> list[str]:
        """Unique EMF ``.ecore`` resources to register, in declaration order."""
        resources: list[str] = []
        for model in self.models:
            resource = model.metamodel_resource
            if model.kind == "emf" and resource and resource not in resources:
                resources.append(resource)
        return resources
