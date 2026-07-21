"""Generate deterministic Java tests from semantic-case artifacts.

Public facade for the extraction pipeline. The god-module this replaced is now
split into focused submodules: `parsing` (parse/validate), `normalization`
(schema-variant coercion), `legacy_adapter` (Tree2Graph), `spec` (shared
accessors), and the sibling `etl.codegen` package (Java harness emitter).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_class_name
from llm4mtl.semantic_tests.codegen.java import render_semantic_test
from llm4mtl.task_contracts import enforce_contract, load_task_contract

from llm4mtl.semantic_tests.semantic_spec import CONTRACT_VIOLATIONS_FILE, SEMANTIC_CASES_FILE

from .parsing import parse_semantic_cases

__all__ = [
    "EnforcementOutcome",
    "augment_with_generated_java",
    "can_generate_java_from_semantic_cases",
    "parse_semantic_cases",
    "render_semantic_test",
    "SEMANTIC_CASES_FILE",
    "CONTRACT_VIOLATIONS_FILE",
]


@dataclass(frozen=True)
class EnforcementOutcome:
    """Result of applying the task contract to a generated suite."""

    applied: bool
    valid: bool
    violations: list[str] = field(default_factory=list)


def can_generate_java_from_semantic_cases(target_task: str) -> bool:
    return True


def augment_with_generated_java(
    target_task: str,
    extracted: dict[str, str],
) -> tuple[dict[str, str], EnforcementOutcome]:
    cases_json = extracted.get(SEMANTIC_CASES_FILE)
    if not cases_json:
        return extracted, EnforcementOutcome(applied=False, valid=True)

    spec = parse_semantic_cases(cases_json, target_task)
    generated = dict(extracted)

    # Infrastructure bindings (metamodel URIs, runtime model names, ecore files,
    # XML namespaces) are owned by the task contract, not the LLM. Rewrite them
    # deterministically and reject assertions over undefined types.
    contract = load_task_contract(target_task)
    violations: list[str] = []
    if contract is not None:
        violations = enforce_contract(contract, spec, generated)
    outcome = EnforcementOutcome(
        applied=contract is not None,
        valid=not violations,
        violations=violations,
    )

    # Persist the normalized, contract-enforced spec for inspection.
    generated[SEMANTIC_CASES_FILE] = json.dumps(spec, indent=2) + "\n"

    # Plan B: semantic cases are the source of truth. Ignore any Java emitted by
    # the LLM and replace it with the deterministic harness.
    for path in list(generated):
        if path.endswith(".java"):
            del generated[path]

    if outcome.valid:
        class_name = sanitize_class_name(
            str(spec.get("testClass") or f"Generated{target_task}SemanticTest"),
            target_task,
        )
        generated[f"{class_name}.java"] = render_semantic_test(class_name, spec, target_task)
    else:
        # A contract-invalid suite must not reach Maven; record why instead of
        # emitting a harness that would fail with a cryptic EMF error.
        generated[CONTRACT_VIOLATIONS_FILE] = (
            json.dumps({"task": target_task, "violations": outcome.violations}, indent=2) + "\n"
        )

    return generated, outcome
