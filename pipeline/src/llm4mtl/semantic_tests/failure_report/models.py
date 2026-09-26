"""Constants of the failure-report documents.

Two report types, kept apart by what the run was able to attribute the failure
to. A per-case report is about one test case and, for an assertion failure, one
assertion. A pair-level report is about the execution of one suite against one
transformation and nothing narrower: it exists for failures that happened before
Surefire could attribute anything to a test method, and it names no case and no
assertion rather than inventing one to fill the shape.
"""

from __future__ import annotations

import re

SCHEMA_VERSION = "1.0"
CASE_REPORT_TYPE = "semantic_test_case_failure"
PAIR_REPORT_TYPE = "semantic_execution_pair_failure"
# The two report scopes. The diagnosis index records the same words.
CASE_SCOPE = "test_case"
PAIR_SCOPE = "execution_pair"
# The ``kind`` of a recorded failure. An assertion failure is a check that ran
# and lost. A runtime error is a throw before any check gave a verdict.
ASSERTION_FAILURE_KIND = "assertion_failure"
RUNTIME_ERROR_KIND = "runtime_error"
# The ``failure_kind`` a pair-level bundle states: no test method was reached.
PAIR_FAILURE_KIND = "execution_pair_failure"
SYSTEM_ERR_EXCERPT_CHARS = 4000
DIFF_FIELDS = (
    "missing_elements",
    "extra_elements",
    "wrong_types",
    "wrong_attributes",
    "reference_mismatches",
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# JUnit prints a failed equality assertion as
# ``<message> ==> expected: <X> but was: <Y>``. Reading X and Y back only copies
# what the harness printed. A message without exactly this shape gives ``None``
# for both; nothing is guessed from the text.
ASSERTION_OUTCOME_SEPARATOR = " but was: <"
ASSERTION_OUTCOME_PREFIX = "expected: <"
# How ``expected``/``actual`` were obtained: read from that JUnit message, or
# not available at all.
JUNIT_MESSAGE_EXTRACTION = "junit_assertion_message"
NO_EXTRACTION = "unavailable"

# The report keeps only the tail of the Maven log; the full log is archived
# beside the observation. A build log can have thousands of lines, and copying
# it into every report of one execution, and then into the diagnosis prompt,
# would bury the useful evidence. The tail holds the failure summary and the
# `[ERROR]` lines.
EXECUTION_LOG_EXCERPT_LINES = 120
EXECUTION_LOG_EXCERPT_CHARS = 8000
# The diagnosis prompt gets less than the report keeps: only the lines Maven
# itself marked, and only the last of those.
MAVEN_BUNDLE_LINES = 40
GENERATED_EXECUTION_LABEL = "generated execution"

PAIR_REQUEST_FIELDS = frozenset(
    {
        "attempt",
        "execution_evidence",
        "execution_log",
        "generated_execution",
        "reference_execution",
        "run_manifest",
        "surefire_reports",
        "syntax_evidence",
    }
)
# A per-case request is a pair-level request plus what names the case.
CASE_REQUEST_FIELDS = PAIR_REQUEST_FIELDS | frozenset(
    {
        "actual_target_models",
        "actual_vs_expected",
        "assertion_id",
        "test_case_id",
    }
)
