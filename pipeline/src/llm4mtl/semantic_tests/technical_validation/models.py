"""CSV columns of the generated-suite technical-validation results."""

from __future__ import annotations

# `assertions_passed` is recorded but is NOT part of the technical verdict: it is
# the oracle observation that reference validation classifies.
RESULT_COLUMNS = [
    "language",
    "task",
    "suite_id",
    "llm",
    "strategy",
    "artifact_valid",
    "compiles",
    "models_load",
    "junit_executes",
    "assertions_passed",
    "technically_valid",
    "status",
    "failure_stage",
    "maven_exit_code",
    "error_summary",
]
