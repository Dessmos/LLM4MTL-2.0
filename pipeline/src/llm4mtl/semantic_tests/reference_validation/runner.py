"""Reference validation: is a generated suite a reference-passing candidate oracle?

This stage classifies the observation produced by executing the suite against the
trusted reference transformation. It reuses the observation technical validation
already recorded for exactly these inputs, and executes only when there is none —
so the two stages report two facts about ONE execution rather than running the
harness twice and risking two different answers.

A suite that could not be executed is not a wrong oracle: it is a suite whose
oracle has not been judged.
"""

from __future__ import annotations

from llm4mtl.domain import GeneratedSuite
from llm4mtl.semantic_tests.validation import (
    ARTIFACT_INVALID,
    VALIDATED,
    SuiteVerdict,
    ValidationContext,
    judge_oracle,
    observe_suite,
)


def validate_suite(
    suite: GeneratedSuite,
    context: ValidationContext,
) -> SuiteVerdict:
    """Judge the immutable candidate; the run observation stores the decision."""
    return judge_oracle(observe_suite(suite, context))


def reference_row(verdict: SuiteVerdict) -> dict[str, str]:
    """The CSV projection of one oracle verdict."""
    observation = verdict.observation
    return {
        "language": verdict.suite.language,
        "task": verdict.suite.task,
        "suite_id": verdict.suite.suite_id,
        "llm": verdict.suite.llm,
        "strategy": verdict.suite.strategy,
        "compiles": str(bool(observation and observation.compiled)),
        "executes": str(bool(observation and observation.tests_discovered)),
        "reference_pass": str(verdict.status == VALIDATED),
        "valid": str(verdict.status == VALIDATED),
        "maven_exit_code": str(observation.maven_exit_code) if observation else "",
        "status": verdict.status,
        "failure_stage": verdict.failure_stage,
        "error_summary": verdict.error_summary,
    }


def is_artifact_invalid(verdict: SuiteVerdict) -> bool:
    return verdict.status == ARTIFACT_INVALID
