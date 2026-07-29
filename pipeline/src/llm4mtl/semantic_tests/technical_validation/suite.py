"""Technical validation of one extracted candidate suite.

Technical validation answers one question: can this generated suite be executed
at all? It deliberately does NOT judge whether the generated assertions are
right — a suite that compiles, runs, and then fails its assertions is
technically valid and is exactly the population reference validation exists to
judge.

The verdict itself comes from :mod:`llm4mtl.semantic_tests.validation`; this
module only turns it into the stage's CSV row.
"""

from __future__ import annotations

from llm4mtl.semantic_tests.validation import (
    ARTIFACT_INVALID,
    SuiteVerdict,
    ValidationContext,
    observe_suite,
)
from llm4mtl.domain import GeneratedSuite


def check_suite(suite: GeneratedSuite, context: ValidationContext) -> SuiteVerdict:
    return observe_suite(suite, context)


def technical_row(verdict: SuiteVerdict) -> dict[str, str]:
    """The CSV projection of one technical verdict."""
    observation = verdict.observation
    return {
        "language": verdict.suite.language,
        "task": verdict.suite.task,
        "suite_id": verdict.suite.suite_id,
        "llm": verdict.suite.llm,
        "strategy": verdict.suite.strategy,
        "artifact_valid": str(verdict.status != ARTIFACT_INVALID),
        "compiles": str(bool(observation and observation.compiled)),
        "models_load": str(bool(observation and observation.models_loaded)),
        "junit_executes": str(bool(observation and observation.tests_discovered)),
        "assertions_passed": str(bool(observation and observation.assertions_passed)),
        "technically_valid": str(verdict.is_technically_executable),
        "status": verdict.status,
        "failure_stage": verdict.failure_stage,
        "maven_exit_code": str(observation.maven_exit_code) if observation else "",
        "error_summary": verdict.error_summary,
    }
