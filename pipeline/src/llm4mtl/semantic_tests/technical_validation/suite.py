"""Technical validation of one extracted candidate suite.

Technical validation answers one question: can this generated suite be executed
at all? It deliberately does NOT judge whether the generated assertions are
right — a suite that compiles, runs, and then fails its assertions is
technically valid and is exactly the population reference validation exists to
judge.

The verdict itself comes from :mod:`llm4mtl.semantic_tests.validation`.
"""

from __future__ import annotations

from llm4mtl.semantic_tests.validation import (
    SuiteVerdict,
    ValidationContext,
    observe_suite,
)
from llm4mtl.domain import GeneratedSuite


def check_suite(suite: GeneratedSuite, context: ValidationContext) -> SuiteVerdict:
    return observe_suite(suite, context)
