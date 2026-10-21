"""Representation normalization for an LLM-authored semantic-case document.

This module may change how a specification is written. It may never change what
the specification says.

RQ1 measures the quality of LLM-generated tests: are they executable, and do
they pass reference validation? Any repair made here would be scored as if the
model had produced it, so quietly fixing a malformed assertion would measure the
pipeline, not the model. The prompt contract
(``prompt_assets/tests/contract/<language>/semantic_cases_contract.txt``) tells
the models that a deviating response is rejected as an invalid artifact.

Allowed here (representation):

* canonical ``schemaVersion`` spelling;
* transformation path and extension canonicalization;
* metamodel declarations resolved to resource paths;
* spec-level ``models`` materialized onto each test that does not override them.

Not allowed here (semantics), and deliberately absent:

* one assertion kind rewritten into another;
* a missing required field filled in from a different field or from a default;
* a model, metamodel, or assertion the response never declared.

A specification that needs any of those is invalid, and saying so is the point:
``parse_semantic_cases`` raises :class:`SemanticCasesError`, the extractor
records the candidate as ``INVALID_SEMANTIC_CASES``, the workflow continues, and
the RQ1 artifact-validity rate drops by exactly that candidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llm4mtl.task_contracts.models import METAMODEL_FILE_SUFFIX

# A bare transformation file name is placed in this resource folder.
TRANSFORMATIONS_DIRECTORY = "transformations"
# A metamodel declared by name or URI resolves to a file in this folder.
METAMODELS_DIRECTORY = "metamodels"


def normalize_schema_variants(
    spec: dict[str, Any], *, transformation_extension: str
) -> dict[str, Any]:
    """Canonicalize how ``spec`` is written, leaving what it asserts untouched.

    ``assertions`` are copied through verbatim. Whatever the response wrote is
    what validation judges.
    """
    normalized = dict(spec)
    schema_version = normalized.pop(
        "schema_version", normalized.get("schemaVersion", 1)
    )
    normalized["schemaVersion"] = _canonical_schema_version(schema_version)

    if "transformation" in normalized:
        normalized["transformation"] = normalize_transformation(
            normalized["transformation"], transformation_extension
        )
    if "metamodels" in normalized:
        normalized["metamodels"] = normalize_metamodels(normalized["metamodels"])
    if "models" in normalized:
        normalized["models"] = normalize_models(normalized["models"])

    normalized["tests"] = [
        _normalize_test(test, normalized.get("models", []))
        for test in normalized.get("tests", [])
    ]
    return normalized


def _canonical_schema_version(raw: Any) -> Any:
    """Write the version ``1`` as the number 1. Any other value is kept."""
    if isinstance(raw, str) and raw in {"1", "1.0"}:
        return 1
    return raw


def _normalize_test(test: Any, spec_models: Any) -> Any:
    """Give a test its own copy of its models, or of the spec-level models."""
    if not isinstance(test, dict):
        # Left exactly as written; validation rejects it with a clear reason
        # rather than this module quietly dropping it from the document.
        return test
    normalized_test = dict(test)
    normalized_test["models"] = normalize_models(
        test["models"] if "models" in test else spec_models
    )
    return normalized_test


def normalize_transformation(raw: Any, extension: str) -> Any:
    """Canonicalize a transformation path. Anything else is passed through.

    A non-string is returned unchanged so validation can report the actual
    shape the response used. There is no default: the deterministic task
    contract supplies the transformation during enforcement, and guessing one
    here would hide a response that never named it.
    """
    if isinstance(raw, str) and raw.strip():
        return normalize_transformation_path(raw.strip(), extension)
    return raw


def normalize_transformation_path(path: str, extension: str) -> str:
    """Canonicalize a non-empty transformation path and its extension."""
    if not extension.startswith("."):
        extension = f".{extension}"
    normalized = path.replace("\\", "/").lstrip("/")
    suffix = Path(normalized).suffix
    if not suffix:
        normalized = f"{normalized}{extension}"
    elif suffix != extension:
        normalized = f"{Path(normalized).with_suffix('')}{extension}"
    if "/" not in normalized:
        normalized = f"{TRANSFORMATIONS_DIRECTORY}/{normalized}"
    return normalized


def normalize_metamodels(raw: Any) -> Any:
    """Resolve declared metamodels to resource paths.

    The declaration itself is not changed: an entry naming no resource at all is
    passed through so the contract check can reject the document instead of this
    module inventing a path for it.
    """
    if not isinstance(raw, list):
        return raw
    return [_normalize_metamodel(item) for item in raw]


def _normalize_metamodel(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    if item.get("path"):
        return str(item["path"])
    if item.get("uri"):
        return f"{METAMODELS_DIRECTORY}/{item['uri']}{METAMODEL_FILE_SUFFIX}"
    if item.get("name"):
        return f"{METAMODELS_DIRECTORY}/{item['name']}{METAMODEL_FILE_SUFFIX}"
    return item


def normalize_models(raw: Any) -> Any:
    """Materialize the declared model list without changing what it declares.

    Entries are copied, never coerced and never dropped. A malformed entry
    reaches validation, which names it; silently removing it would turn a
    defective specification into a smaller valid-looking one.
    """
    if not isinstance(raw, list):
        return raw
    return [dict(model) if isinstance(model, dict) else model for model in raw]
