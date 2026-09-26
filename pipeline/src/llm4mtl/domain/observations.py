"""Facts a stage observed, independent of the language that produced them.

These are the raw observations every metric is later derived from, so each one
keeps its questions separate. In particular a suite execution answers three
independent questions — is the artifact usable, did it run, did its assertions
hold — and collapsing them is what makes a reference-pass rate stop meaning what
it claims to mean.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Why a generated suite cannot become an executable test.
#
# EXTRACTION_FAILED is recorded before any specification is read: the response's
# file blocks could not be resolved to an unambiguous artifact set. The candidate
# is still persisted so the response stays in the funnel's denominator, but it
# carries no artifacts and is never executed.
EXTRACTION_FAILED = "EXTRACTION_FAILED"
MISSING_SEMANTIC_CASES = "MISSING_SEMANTIC_CASES"
INVALID_SEMANTIC_CASES = "INVALID_SEMANTIC_CASES"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
# The reason code of a rendered suite that fails a static check. It is also the
# fallback when a recorded invalid verdict names no reason.
ARTIFACT_INVALID_REASON = "ARTIFACT_INVALID"


class FailureStage:
    """The values of ``SuiteExecutionObservation.failure_stage``.

    Plain strings, not an enum, because they are persisted:
    ``schemas/suite-execution.schema.json`` lists them. An empty string means no
    phase failed.
    """

    ARTIFACT_VALIDATION = "artifact_validation"
    JAVA_COMPILATION = "java_compilation"
    TEST_DISCOVERY = "test_discovery"
    MODEL_LOADING = "model_loading"
    TRANSFORMATION_PARSE = "transformation_parse"
    ENGINE_RUNTIME = "engine_runtime"
    # The run threw, but nothing in the error names the phase. Never a phase claim.
    UNCLASSIFIED_RUNTIME = "unclassified_runtime"
    ASSERTION_FAILURE = "assertion_failure"
    TIMEOUT = "timeout"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class ArtifactValidation:
    """Whether a generated suite is a usable artifact at all.

    The first gate of the validation funnel, and independent of both technical
    executability and oracle validity: an artifact-invalid suite is never
    executed, so neither of those questions is ever asked about it.
    """

    valid: bool
    reason_code: str = ""
    violations: tuple[str, ...] = ()
    contract_applied: bool = False

    def as_metadata(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "reason_code": self.reason_code,
            "violations": list(self.violations),
            "contract_applied": self.contract_applied,
        }


@dataclass(frozen=True)
class ParseObservation:
    """Whether a transformation is syntactically accepted by its language parser.

    ``problem_count`` is ``None`` when the parser reported no count, and an
    integer only when it measured one. A missing count is not zero problems: an
    errors-per-LOC figure that used zero would understate exactly the runs
    where the parser failed to report. So ``None`` is the default, and a
    producer that measures a count states it.

    ``parsed`` is a separate fact: a transformation can be parsed while its
    count is still ``None``.
    """

    parsed: bool
    problem_count: int | None = None
    diagnostic: str = ""


@dataclass(frozen=True)
class SuiteExecutionObservation:
    """What one execution of a rendered suite established, as separate facts."""

    compiled: bool
    tests_discovered: bool
    models_loaded: bool
    engine_started: bool
    assertions_evaluated: bool
    assertions_passed: bool
    timed_out: bool
    maven_exit_code: int | str
    failure_stage: str
    error_summary: str

    @property
    def is_technically_executable(self) -> bool:
        """The run reached a verdict about the assertions.

        A suite whose engine threw before judging anything is not executable,
        even when earlier phases succeeded. Counting it would put a test that
        can never give an oracle verdict into the numerator.
        """
        return (
            self.compiled
            and self.tests_discovered
            and self.models_loaded
            and self.engine_started
            and self.assertions_evaluated
            and not self.timed_out
        )

    @property
    def is_reference_valid(self) -> bool:
        """The suite is a reference-passing candidate oracle."""
        return self.is_technically_executable and self.assertions_passed

    @property
    def is_infrastructure_failure(self) -> bool:
        """The run says nothing about the suite because the harness itself broke."""
        return self.failure_stage in {
            FailureStage.TIMEOUT,
            FailureStage.TRANSFORMATION_PARSE,
            FailureStage.INFRASTRUCTURE,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "compiled": self.compiled,
            "tests_discovered": self.tests_discovered,
            "models_loaded": self.models_loaded,
            "engine_started": self.engine_started,
            "assertions_evaluated": self.assertions_evaluated,
            "assertions_passed": self.assertions_passed,
            "timed_out": self.timed_out,
            "maven_exit_code": self.maven_exit_code,
            "failure_stage": self.failure_stage,
            "error_summary": self.error_summary,
            "technically_executable": self.is_technically_executable,
            "reference_valid": self.is_reference_valid,
        }

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return (
            "compiled",
            "tests_discovered",
            "models_loaded",
            "engine_started",
            "assertions_evaluated",
            "assertions_passed",
            "timed_out",
            "maven_exit_code",
            "failure_stage",
            "error_summary",
        )
