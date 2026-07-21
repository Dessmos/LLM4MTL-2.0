"""Validation of LLM-generated transformations with reference-validated suites.

Public API (facade); import from this package rather than its submodules.
"""

from llm4mtl.transformation_execution.artifacts import archive_result
from llm4mtl.transformation_execution.discovery import (
    discover_transformations,
    discover_validated_suites,
    match_pairs,
)
from llm4mtl.transformation_execution.models import TransformationValidationResult
from llm4mtl.transformation_execution.results import write_results
from llm4mtl.transformation_execution.executor import failure_stage

__all__ = [
    "archive_result",
    "discover_transformations",
    "discover_validated_suites",
    "match_pairs",
    "TransformationValidationResult",
    "write_results",
    "failure_stage",
]
