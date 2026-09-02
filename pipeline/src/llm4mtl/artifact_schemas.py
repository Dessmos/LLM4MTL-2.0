"""Validation of persisted artifacts against the canonical JSON Schemas.

``schemas/`` is the contract shared by n8n, Python, and the stored experiment
evidence. Until now nothing enforced it, so schemas documented an intent the
writers had drifted away from. Every store that persists a scientific artifact
validates it here *before* writing, so a divergence fails loudly at the moment
it is introduced instead of silently corrupting a run.

Validation is deliberately strict: a schema violation is a defect in the writer
or in the schema, never something to repair at runtime.

Versioning policy
-----------------
Each persisted artifact pins its ``schema_version`` with ``const``. A change that
alters the meaning of an existing field, removes one, or changes what a reader
must accept is breaking: bump the version, and old artifacts then fail validation
loudly instead of being silently reinterpreted. Runs are regenerable output under
``artifacts/work/``, so the migration for a breaking change is to re-run rather
than to rewrite stored evidence — rewriting it would make a past result
unreproducible from the code that produced it.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from llm4mtl.paths import TARGET


class ArtifactSchemaError(ValueError):
    """Raised when a payload does not conform to its declared schema."""


FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks("date-time", raises=(TypeError, ValueError))
def _is_rfc3339_date_time(value: object) -> bool:
    """Validate the RFC 3339 subset emitted by this repository.

    ``jsonschema`` only installs its date-time checker when an optional package
    is present. Registering this small checker keeps format validation active in
    the project's declared base dependency instead of silently accepting every
    string on installations without that extra.
    """
    if not isinstance(value, str):
        return True
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    return parsed.tzinfo is not None


# Artifact id -> schema file under ``schemas/``. The id is the vocabulary used by
# callers; the filename is an implementation detail of the schema directory.
SCHEMA_FILES: dict[str, str] = {
    "manifest": "manifest.schema.json",
    "events": "events.schema.json",
    "stage-result": "stage-result.schema.json",
    "experiment-manifest": "experiment-manifest.schema.json",
    "run-index": "run-index.schema.json",
    "diagnosis": "diagnosis.schema.json",
    "suite-execution": "suite-execution.schema.json",
    "execution-evidence": "execution-evidence.schema.json",
    "generation-result": "generation-result.schema.json",
    "semantic-cases": "semantic_cases.schema.json",
    "contract": "contract.schema.json",
    "run-result": "run-result.schema.json",
    "transformation-adoption": "transformation-adoption.schema.json",
    "refinement-request": "refinement-request.schema.json",
    "failure-report": "failure-report.schema.json",
    "diagnosis-index": "diagnosis-index.schema.json",
}


@lru_cache(maxsize=None)
def _validator(artifact: str) -> Draft202012Validator:
    try:
        filename = SCHEMA_FILES[artifact]
    except KeyError as exc:
        known = ", ".join(sorted(SCHEMA_FILES))
        raise ArtifactSchemaError(
            f"unknown artifact schema '{artifact}' (known: {known})"
        ) from exc
    schema = json.loads((TARGET.schemas / filename).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FORMAT_CHECKER)


def validate_artifact(artifact: str, payload: Mapping[str, Any]) -> None:
    """Raise :class:`ArtifactSchemaError` unless ``payload`` conforms to ``artifact``."""
    errors = sorted(
        _validator(artifact).iter_errors(payload), key=lambda error: list(error.path)
    )
    if not errors:
        return
    details = "; ".join(
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in errors
    )
    raise ArtifactSchemaError(
        f"{artifact} payload violates {SCHEMA_FILES[artifact]}: {details}"
    )
