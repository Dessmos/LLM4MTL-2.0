"""Reference-validation support for generated ETL semantic suites.

Public API (facade); import from this package rather than its submodules.
"""

from llm4mtl.semantic_tests.reference_validation.maven_status import compiles, executes
from llm4mtl.semantic_tests.reference_validation.promotion import (
    invalid_suite_path,
    promote_invalid_suite,
)
from llm4mtl.semantic_tests.reference_validation.reference import transformation_destination

__all__ = [
    "invalid_suite_path",
    "promote_invalid_suite",
    "compiles",
    "executes",
    "transformation_destination",
]
