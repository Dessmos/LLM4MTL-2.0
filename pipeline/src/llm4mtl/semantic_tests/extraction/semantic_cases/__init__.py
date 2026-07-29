"""Generate deterministic Java tests from semantic-case artifacts.

Public facade for the extraction pipeline. The god-module this replaced is now
split into focused submodules: `parsing` (parse/validate), `normalization`
(schema-variant coercion), `legacy_adapter` (Tree2Graph), `spec` (shared
accessors), and the sibling `etl.codegen` package (Java harness emitter).

The LLM authors semantic cases and input models; it never authors executable
test infrastructure. Java that arrives in a response is discarded unconditionally
— the harness is rendered here from the validated specification, so an
unrenderable response yields an artifact-invalid suite rather than arbitrary code
that a later stage would compile and run.
"""

from __future__ import annotations

import json
from llm4mtl.domain import (
    CONTRACT_VIOLATION,
    INVALID_SEMANTIC_CASES,
    MISSING_SEMANTIC_CASES,
    ArtifactValidation,
)
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_class_name
from llm4mtl.semantic_tests.codegen.java import render_semantic_test
from llm4mtl.task_contracts import enforce_contract, load_task_contract

from llm4mtl.semantic_tests.scenario_mapping import ScenarioMappingError, suite_from_spec
from llm4mtl.semantic_tests.semantic_spec import CONTRACT_VIOLATIONS_FILE, SEMANTIC_CASES_FILE

from .errors import SemanticCasesError
from .parsing import parse_semantic_cases

__all__ = [
    "ArtifactValidation",
    "MISSING_SEMANTIC_CASES",
    "CONTRACT_VIOLATION",
    "render_generated_suite",
    "parse_semantic_cases",
    "render_semantic_test",
    "SEMANTIC_CASES_FILE",
    "CONTRACT_VIOLATIONS_FILE",
]

def render_generated_suite(
    target_task: str,
    extracted: dict[str, str],
    *,
    language: str,
) -> tuple[dict[str, str], ArtifactValidation]:
    """Replace LLM-authored files with a deterministically rendered suite.

    Returns the files to write and why the suite is (in)valid. Any ``.java`` the
    model produced is dropped in every path; the only Java that can survive is
    the harness rendered here from the validated specification.
    """
    generated = {path: content for path, content in extracted.items() if not path.endswith(".java")}

    cases_json = extracted.get(SEMANTIC_CASES_FILE)
    if not cases_json:
        return generated, ArtifactValidation(
            valid=False,
            reason_code=MISSING_SEMANTIC_CASES,
            violations=(
                f"no {SEMANTIC_CASES_FILE} in the response: there is no specification "
                "to render an executable test from"
            ),
        )

    try:
        spec = parse_semantic_cases(cases_json, target_task)
    except SemanticCasesError as exc:
        return generated, ArtifactValidation(
            valid=False,
            reason_code=INVALID_SEMANTIC_CASES,
            violations=(str(exc),),
        )

    # Infrastructure bindings (metamodel URIs, runtime model names, ecore files,
    # XML namespaces) are owned by the task contract, not the LLM. Rewrite them
    # deterministically and reject assertions over undefined types.
    contract = load_task_contract(target_task)
    violations: list[str] = []
    if contract is not None:
        violations = enforce_contract(contract, spec, generated)

    # Persist the normalized, contract-enforced spec for inspection.
    generated[SEMANTIC_CASES_FILE] = json.dumps(spec, indent=2) + "\n"

    # The suite must be expressible in the shared scenario contract before it may
    # execute. A suite the ETL path accepts but the contract cannot describe is a
    # defect in the contract, and it has to surface here rather than leave the
    # shared representation quietly ETL-shaped.
    try:
        suite_from_spec(
            spec,
            suite_id="candidate",
            language=language,
            task=target_task,
        )
    except ScenarioMappingError as exc:
        violations = [*violations, str(exc)]

    if violations:
        # A contract-invalid suite must not reach Maven; record why instead of
        # emitting a harness that would fail with a cryptic EMF error.
        generated[CONTRACT_VIOLATIONS_FILE] = (
            json.dumps({"task": target_task, "violations": violations}, indent=2) + "\n"
        )
        return generated, ArtifactValidation(
            valid=False,
            reason_code=CONTRACT_VIOLATION,
            violations=tuple(violations),
            contract_applied=True,
        )

    class_name = sanitize_class_name(
        str(spec.get("testClass") or f"Generated{target_task}SemanticTest"),
        target_task,
    )
    generated[f"{class_name}.java"] = render_semantic_test(class_name, spec, target_task)
    return generated, ArtifactValidation(valid=True, contract_applied=contract is not None)
