"""Turn an extracted ``semantic_cases.json`` into a validated spec and a Java harness.

Public facade over the submodules `parsing` (parse and validate),
`normalization` (representation cleanup) and `legacy_adapter` (old Tree2Graph
shape). Shared spec accessors live in :mod:`llm4mtl.semantic_tests.semantic_spec`;
the Java harness is written by each language's ``rendering`` module, using
:mod:`llm4mtl.semantic_tests.codegen`.

The LLM writes semantic cases and input models, never executable test code.
Any Java in a response is always dropped; the harness is rendered from the
validated spec. A spec that cannot be rendered gives an artifact-invalid suite,
not arbitrary code that a later stage would compile and run.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from llm4mtl.conventions import LanguageConfig
from llm4mtl.domain import (
    CONTRACT_VIOLATION,
    INVALID_SEMANTIC_CASES,
    MISSING_SEMANTIC_CASES,
    ArtifactValidation,
)
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_class_name
from llm4mtl.task_contracts import TaskContract, enforce_contract, load_task_contract

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
    "SEMANTIC_CASES_FILE",
    "CONTRACT_VIOLATIONS_FILE",
]


_MISSING_SEMANTIC_CASES = ArtifactValidation(
    valid=False,
    reason_code=MISSING_SEMANTIC_CASES,
    violations=(
        f"no {SEMANTIC_CASES_FILE} in the response: there is no specification "
        "to render an executable test from",
    ),
)


def render_generated_suite(
    target_task: str,
    extracted: dict[str, str],
    *,
    language: str,
    config: LanguageConfig,
    transformation_extension: str,
    render_test: Callable[[str, dict[str, object], str], str],
) -> tuple[dict[str, str], ArtifactValidation]:
    """Replace LLM-authored files with a deterministically rendered suite.

    Every language argument is required, so an adapter cannot silently render
    ETL conventions under another language's name.

    Returns the files to write and why the suite is (in)valid. Any ``.java`` the
    model produced is dropped in every path; the only Java that can survive is
    the harness rendered here from the validated specification.
    """
    generated = _without_java(extracted)
    cases_json = extracted.get(SEMANTIC_CASES_FILE)
    if not cases_json:
        return generated, _MISSING_SEMANTIC_CASES
    try:
        spec = parse_semantic_cases(
            cases_json, transformation_extension=transformation_extension
        )
    except SemanticCasesError as exc:
        return generated, ArtifactValidation(
            valid=False, reason_code=INVALID_SEMANTIC_CASES, violations=(str(exc),)
        )
    contract = load_task_contract(target_task, config=config)
    violations = _contract_violations(spec, generated, contract, language, target_task)
    if violations:
        return generated, _record_violations(generated, target_task, violations)
    _render_harness(spec, generated, target_task, render_test)
    return generated, ArtifactValidation(
        valid=True, contract_applied=contract is not None
    )


def _without_java(extracted: dict[str, str]) -> dict[str, str]:
    """Drop every Java file the model wrote; only the rendered harness may run."""
    return {
        path: content
        for path, content in extracted.items()
        if not path.endswith(".java")
    }


def _contract_violations(
    spec: dict[str, object],
    generated: dict[str, str],
    contract: TaskContract | None,
    language: str,
    task: str,
) -> list[str]:
    """Enforce the task contract, then list everything that breaks a contract.

    Also stores the enforced spec in ``generated``.
    """
    violations: list[str] = []
    if contract is not None:
        # The task contract, not the LLM, owns infrastructure bindings
        # (metamodel URIs, runtime model names, ecore files, XML namespaces).
        # Rewrite them and reject assertions over undefined types.
        violations = enforce_contract(contract, spec, generated)
    # Persist the normalized, contract-enforced spec for inspection.
    generated[SEMANTIC_CASES_FILE] = json.dumps(spec, indent=2) + "\n"
    return [
        *violations,
        *_scenario_mapping_violations(spec, language=language, task=task),
    ]


def _scenario_mapping_violations(
    spec: dict[str, object], *, language: str, task: str
) -> list[str]:
    """Why ``spec`` cannot be expressed in the shared scenario contract, if at all.

    A suite that a language's renderer accepts but the contract cannot describe
    shows a defect in the contract. It must surface here, before the suite can
    run, so the shared contract does not quietly fit only one language.
    """
    try:
        suite_from_spec(spec, suite_id="candidate", language=language, task=task)
    except ScenarioMappingError as exc:
        return [str(exc)]
    return []


def _record_violations(
    generated: dict[str, str], task: str, violations: list[str]
) -> ArtifactValidation:
    """Record why the suite breaks its contract, instead of rendering a harness.

    A contract-invalid suite must not reach Maven, where it would fail with a
    cryptic EMF error.
    """
    generated[CONTRACT_VIOLATIONS_FILE] = (
        json.dumps({"task": task, "violations": violations}, indent=2) + "\n"
    )
    return ArtifactValidation(
        valid=False,
        reason_code=CONTRACT_VIOLATION,
        violations=tuple(violations),
        contract_applied=True,
    )


def _render_harness(
    spec: dict[str, object],
    generated: dict[str, str],
    task: str,
    render_test: Callable[[str, dict[str, object], str], str],
) -> None:
    """Add the test class rendered from ``spec`` to ``generated``."""
    class_name = sanitize_class_name(
        str(spec.get("testClass") or f"Generated{task}SemanticTest"), task
    )
    generated[f"{class_name}.java"] = render_test(class_name, spec, task)
