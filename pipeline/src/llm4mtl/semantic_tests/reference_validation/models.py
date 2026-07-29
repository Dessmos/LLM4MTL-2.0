"""Constants for reference validation.

The verdict type and the status vocabulary live in
:mod:`llm4mtl.semantic_tests.validation`, which both gates share; only the CSV
projection of this stage is defined here.
"""

from __future__ import annotations

# NOT_EXECUTABLE and ARTIFACT_INVALID mean the oracle question could not be
# asked; only VALIDATED and REFERENCE_INVALID are verdicts about the generated
# oracle, and only they belong in the reference-pass population.
RESULT_COLUMNS = [
    "language",
    "task",
    "suite_id",
    "llm",
    "strategy",
    "compiles",
    "executes",
    "reference_pass",
    "valid",
    "maven_exit_code",
    "status",
    "failure_stage",
    "error_summary",
]
