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
SYSTEM_ERR_EXCERPT_CHARS = 4000
DIFF_FIELDS = (
    "missing_elements",
    "extra_elements",
    "wrong_types",
    "wrong_attributes",
    "reference_mismatches",
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")

# JUnit renders a failed equality assertion as
# ``<message> ==> expected: <X> but was: <Y>``. Reading X and Y back is
# observation, not inference: the values are the ones the harness printed. Any
# message that does not have exactly this shape yields ``None`` for both rather
# than a guess reconstructed from prose.
ASSERTION_OUTCOME_SEPARATOR = " but was: <"
ASSERTION_OUTCOME_PREFIX = "expected: <"

# The report cites the Maven log rather than copying it. The complete,
# untruncated stream is already archived beside the observation, and a build log
# can run to thousands of lines: inlining it would put the same bytes into every
# per-assertion report of the same execution and then into the diagnosis prompt,
# where it drowns the evidence Python already extracted. The tail is what
# carries the failure summary and the `[ERROR]` lines.
EXECUTION_LOG_EXCERPT_LINES = 120
EXECUTION_LOG_EXCERPT_CHARS = 8000
# The diagnosis prompt gets less than the report keeps: only the lines Maven
# itself marked, and only the last of those.
MAVEN_BUNDLE_LINES = 40
GENERATED_EXECUTION_LABEL = "generated execution"

CASE_REQUEST_FIELDS = frozenset(
    {
        "actual_target_models",
        "actual_vs_expected",
        "assertion_id",
        "attempt",
        "execution_evidence",
        "execution_log",
        "generated_execution",
        "reference_execution",
        "run_manifest",
        "surefire_reports",
        "syntax_evidence",
        "test_case_id",
    }
)
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
