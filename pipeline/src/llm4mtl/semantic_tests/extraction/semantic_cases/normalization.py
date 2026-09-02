"""Representation normalization for an LLM-authored semantic-case document.

This module may change how a specification is written. It may never change what
the specification says.

That line matters because RQ1 measures the quality of LLM-generated tests: are
they executable, and do they pass reference validation? Every repair applied
here would be measured as if the model had produced it, so a pipeline that
quietly fixes a malformed assertion reports its own competence, not the model's.

The prompt contract the models receive already states the consequence — "a
response that deviates from it is rejected before anything is executed and is
recorded as an invalid artifact, not as a failing test" (see
``prompt_assets/tests/contract/<language>/semantic_cases_contract.txt``). This
module used to contradict that promise: it rewrote one assertion kind into
another, scavenged ``expected`` out of ``where``/``equals``/``match``, guessed
missing ``model``/``type``/``feature`` fields, and invented target models the
response never declared. Those repairs are gone.

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


def normalize_schema_variants(
    spec: dict[str, Any],
    target_task: str,
    *,
    transformation_extension: str = ".etl",
) -> dict[str, Any]:
    """Canonicalize how ``spec`` is written, leaving what it asserts untouched.

    ``assertions`` are copied through verbatim. Whatever the response wrote is
    what validation judges.
    """
    normalized = dict(spec)

    schema_version = normalized.pop(
        "schema_version",
        normalized.get("schemaVersion", 1),
    )
    if isinstance(schema_version, str) and schema_version in {"1", "1.0"}:
        schema_version = 1
    normalized["schemaVersion"] = schema_version

    if "transformation" in normalized:
        normalized["transformation"] = normalize_transformation(
            normalized["transformation"],
            target_task,
            transformation_extension,
        )
    if "metamodels" in normalized:
        normalized["metamodels"] = normalize_metamodels(normalized["metamodels"])
    if "models" in normalized:
        normalized["models"] = normalize_models(normalized["models"])

    tests = []
    for test in normalized.get("tests", []):
        if not isinstance(test, dict):
            # Left exactly as written; validation rejects it with a clear reason
            # rather than this module quietly dropping it from the document.
            tests.append(test)
            continue
        normalized_test = dict(test)
        normalized_test["models"] = normalize_models(
            test["models"] if "models" in test else normalized.get("models", [])
        )
        tests.append(normalized_test)
    normalized["tests"] = tests
    return normalized


def normalize_transformation(
    raw: Any,
    target_task: str,
    extension: str = ".etl",
) -> Any:
    """Canonicalize a transformation path. Anything else is passed through.

    A non-string is returned unchanged so validation can report the actual
    shape the response used. There is no default: the deterministic task
    contract supplies the transformation during enforcement, and guessing one
    here would hide a response that never named it.
    """
    if isinstance(raw, str) and raw.strip():
        return normalize_transformation_path(raw.strip(), target_task, extension)
    return raw


def normalize_transformation_path(
    path: str,
    target_task: str,
    extension: str = ".etl",
) -> str:
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
        normalized = f"transformations/{normalized}"
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
        return f"metamodels/{item['uri']}.ecore"
    if item.get("name"):
        return f"metamodels/{item['name']}.ecore"
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
