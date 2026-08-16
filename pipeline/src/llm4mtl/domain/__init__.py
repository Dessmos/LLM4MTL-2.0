"""Language-neutral core of the pipeline.

This package holds the concepts every language and every metric is expressed in:
scenarios, transformation outcomes, and the observations stages record. It is
pure — no filesystem, no subprocess, no engine — so the semantics can be tested
directly and the evaluation layer can be derived from stored observations alone.

Dependency direction: `domain` depends on nothing in the package. Language
adapters and the pipeline depend on `domain`, never the other way round.
"""

from __future__ import annotations

from llm4mtl.domain.artifacts import ArtifactRef
from llm4mtl.domain.observations import (
    CONTRACT_VIOLATION,
    EXTRACTION_FAILED,
    INVALID_SEMANTIC_CASES,
    MISSING_SEMANTIC_CASES,
    ArtifactValidation,
    ParseObservation,
    SuiteExecutionObservation,
)
from llm4mtl.domain.outcomes import ModelSnapshot, OutcomeStatus, TransformationOutcome
from llm4mtl.domain.scenarios import (
    ChangeKind,
    ChangeOperation,
    ElementRef,
    ElementSpec,
    Expectation,
    ModelRole,
    ModelSlot,
    ScenarioKind,
    SemanticScenario,
    SemanticSuite,
)
from llm4mtl.domain.suites import GeneratedSuite

__all__ = [
    "ArtifactRef",
    "ArtifactValidation",
    "ChangeKind",
    "ChangeOperation",
    "CONTRACT_VIOLATION",
    "EXTRACTION_FAILED",
    "ElementRef",
    "ElementSpec",
    "Expectation",
    "GeneratedSuite",
    "INVALID_SEMANTIC_CASES",
    "MISSING_SEMANTIC_CASES",
    "ModelRole",
    "ModelSlot",
    "ModelSnapshot",
    "OutcomeStatus",
    "ParseObservation",
    "ScenarioKind",
    "SemanticScenario",
    "SemanticSuite",
    "SuiteExecutionObservation",
    "TransformationOutcome",
]
