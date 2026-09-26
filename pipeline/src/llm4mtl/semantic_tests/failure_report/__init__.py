"""Assemble one semantic-test failure report.

The whole interface is ``write_report(payload, output, scope=...)``. The caller
names the kind of failure it recorded and passes the recorded paths:
``"test_case"`` is one test case (and, for an assertion failure, one assertion);
``"execution_pair"`` is a failure the run could not attribute to any test
method. This package picks the request class and the builder.

The package only collects facts that earlier stages recorded. It does not
compare models, classify the source of a failure, call an LLM, or choose a
workflow route. In particular, ``actual_vs_expected`` must come from the
comparator or harness that saw the mismatch; this package never invents it.

Diagnosis preparation calls it once per failure after every execution attempt.

A ``"test_case"`` request is one JSON object with these fields. An
``"execution_pair"`` request is the same without ``test_case_id``,
``assertion_id``, ``actual_target_models`` and ``actual_vs_expected``, because a
failure that reached no test method has none of them::

    {
      "run_manifest": "artifacts/work/runs/<batch>/<run>/manifest.json",
      "syntax_evidence": ".../stages/syntax-validation/.../evidence.json",
      "execution_evidence": ".../stages/execution/attempts/attempt-001/evidence.json",
      "generated_execution": ".../suite_execution.json",
      "reference_execution": ".../suite_execution.json",  # optional
      "test_case_id": "case_name",
      "assertion_id": "assertion-001",
      "attempt": 1,
      "actual_target_models": [".../snapshot.xmi"],
      "surefire_reports": [".../TEST-GeneratedTest.xml"],   # optional, see below
      "execution_log": ".../execution.log",                 # optional
      "actual_vs_expected": {                                # optional, see below
        "missing_elements": [],
        "extra_elements": [],
        "wrong_types": [],
        "wrong_attributes": [],
        "reference_mismatches": []
      }
    }

``actual_vs_expected`` is the model-level comparator difference. It is optional
because no comparator produces it yet. Without it, the report records what the
run observed: the actual target-model snapshots, the ``expected``/``actual``
values JUnit printed (copied as printed), and the recorded exception. When a
failure may be diagnosed is decided in ``eligibility``.

Both JUnit outcomes are real failures. A lost assertion names that assertion. A
throw before any verdict names none: ``assertion_id`` is ``null``, the exception
and stack trace are the evidence, and ``expected``/``actual`` stay ``null``. A
timeout or an infrastructure failure is not diagnosable, because neither says
anything about the pairing.

``assertion_id`` is the assertion's own ``id`` from ``semantic_cases.json``, the
positional id ``assertion-NNN``, or ``null`` for a runtime throw. Input models,
the generated transformation and suite, the task description, and the exact
metamodels are found through the recorded identities. Every input path must be
inside the repository, and the output must be under ``artifacts/work``. The
output is created once and never overwritten.

``surefire_reports`` and ``execution_log`` should normally be left out. The run
archives its Maven output and Surefire XML beside each execution observation,
and after the next ``mvn clean`` that archive is the only copy. Leaving them out
reads the archive; naming them still works for evidence kept elsewhere. A
``"test_case"`` request that leaves out ``surefire_reports`` for an execution
with no archive is refused, so its runtime evidence is never silently empty.

Package layout: ``request`` parses and bounds the request, ``evidence``
resolves the facts both report types share from one recorded execution,
``surefire_view`` projects the archived reports, ``eligibility`` decides whether
Source Diagnosis may be asked, ``semantic_cases`` names cases and assertions,
``report_document`` builds the parts both documents share, and
``case_report`` / ``pair_report`` assemble the two documents. Import from this
package, not from its submodules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from llm4mtl.semantic_tests.failure_report.case_report import write_failure_report
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.models import (
    ASSERTION_FAILURE_KIND,
    CASE_SCOPE,
    DIFF_FIELDS,
    PAIR_SCOPE,
    RUNTIME_ERROR_KIND,
)
from llm4mtl.semantic_tests.failure_report.pair_report import write_pair_failure_report
from llm4mtl.semantic_tests.failure_report.report_document import (
    FAILURE_REPORT_SCHEMA,
)
from llm4mtl.semantic_tests.failure_report.request import request_type
from llm4mtl.semantic_tests.failure_report.semantic_cases import (
    assertion_id,
    case_id,
    rendered_method_name,
)

_WRITERS = {
    CASE_SCOPE: write_failure_report,
    PAIR_SCOPE: write_pair_failure_report,
}


def write_report(
    payload: Mapping[str, Any],
    output: Path,
    *,
    scope: str,
) -> dict[str, Any]:
    """Validate ``payload`` for ``scope``, then build and write the report.

    Returns the written report. Raises :class:`FailureReportError` for an
    unknown scope, an invalid request, or evidence that cannot form a
    trustworthy report.
    """
    request = request_type(scope).from_payload(payload)
    return _WRITERS[scope](request, output)


__all__ = [
    "ASSERTION_FAILURE_KIND",
    "CASE_SCOPE",
    "DIFF_FIELDS",
    "FAILURE_REPORT_SCHEMA",
    "FailureReportError",
    "PAIR_SCOPE",
    "RUNTIME_ERROR_KIND",
    "assertion_id",
    "case_id",
    "rendered_method_name",
    "write_report",
]
