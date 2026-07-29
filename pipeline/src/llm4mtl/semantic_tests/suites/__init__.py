"""Shared generated-suite structures and filesystem helpers.

Public API (facade); import from this package rather than its submodules.
"""

from llm4mtl.semantic_tests.suites.injection import inject_suite, suite_model_paths
from llm4mtl.semantic_tests.suites.java import infer_fqcn, slug
from llm4mtl.domain import GeneratedSuite

__all__ = ["GeneratedSuite", "inject_suite", "suite_model_paths", "infer_fqcn", "slug"]
