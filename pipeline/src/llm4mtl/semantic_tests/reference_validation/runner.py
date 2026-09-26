"""Reference validation: is a generated suite a reference-passing candidate oracle?

This stage classifies the observation of running the suite against the trusted
reference transformation. It reuses the observation technical validation already
recorded for exactly these inputs, and runs Maven only when there is none. So
both stages report on ONE execution instead of running the harness twice and
maybe getting two different answers.

A suite that could not be executed is not a wrong oracle: it is a suite whose
oracle has not been judged.
"""

from __future__ import annotations

from llm4mtl.domain import GeneratedSuite
from llm4mtl.semantic_tests.validation import (
    SuiteVerdict,
    ValidationContext,
    judge_oracle,
    observe_suite,
)


def validate_suite(
    suite: GeneratedSuite,
    context: ValidationContext,
) -> SuiteVerdict:
    """Return the oracle verdict for ``suite``, reusing its recorded observation."""
    return judge_oracle(observe_suite(suite, context))
