"""Assemble one semantic-test failure report.

``write_report(payload, output, scope=...)`` is the whole interface: a caller
names the kind of failure it recorded — ``"test_case"`` for one test case and,
for an assertion failure, one assertion, or ``"execution_pair"`` for a failure
the run could not attribute to any test method — and hands over the paths it
recorded it from. Which request boundary validates the payload and which
assembler builds the document is this package's business.

The package only aggregates facts that earlier stages recorded.  It does not
compare models, classify the source of a failure, call an LLM, or choose a
workflow route.  In particular, ``actual_vs_expected`` must come from the
comparator or harness that observed the mismatch; this package refuses to
invent that evidence.

Run it through the experiment orchestrator with::

    llm4mtl diagnosis report \
      --request request.json --output artifacts/work/.../failure-report.json

The package also keeps a direct
``python -m llm4mtl.semantic_tests.failure_report`` entry point for narrow
local use; both paths call the same assembler.

The ``"test_case"`` request is one JSON object with these fields (an
``"execution_pair"`` request is the same without ``test_case_id``,
``assertion_id``, ``actual_target_models`` and ``actual_vs_expected``, because a
failure that reached no test method has none of them)::

    {
      "run_manifest": "artifacts/work/runs/<run>/manifest.json",
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

``actual_vs_expected`` is the model-level comparator difference.  It is optional
because no comparator produces it yet, and inventing one here is exactly what
this module refuses to do.  What the report records without it is what the run
observed: the actual target-model snapshots the harness wrote, the
``expected``/``actual`` values JUnit printed read verbatim, and the recorded
exception.  A diagnosis-eligible failure needs a syntactically valid
transformation, a suite that passed on the reference, a real failure of the
pairing, the transformed input, and at least one of those observed facts.

Both JUnit outcomes are real failures here.  An assertion that was evaluated and
lost names the assertion it lost; a throw before any verdict names none, and
``assertion_id`` is then ``null`` — the exception and its stack trace are the
evidence, and ``expected``/``actual`` stay ``null`` rather than being
reconstructed.  A timeout or an infrastructure failure is excluded instead,
because neither says anything about the pairing.

``assertion_id`` is either an explicit assertion ``id`` from
``semantic_cases.json``, the stable positional id ``assertion-NNN``, or ``null``
for a runtime throw.  Input
models, the generated transformation and suite, the reviewed task description,
and exact metamodels are resolved from the recorded identities.  Every input
path must stay inside the repository, and the output must stay under
``artifacts/work``.  The output is created once and never overwritten.

``surefire_reports`` and ``execution_log`` may be omitted, and normally should
be: the run archives its own Maven output and Surefire XML beside each execution
observation, and that archive is the only copy that still describes the
execution once the next pair's ``mvn clean`` has run.  Omitting them reads the
archive; naming them explicitly still works for evidence held elsewhere.  A
request that omits them for an execution with no archive is refused rather than
producing a report whose runtime evidence is silently empty.

Package layout: ``request`` parses and bounds the request, ``evidence``
resolves the facts both report types share from one recorded execution,
``surefire_view`` projects the archived reports, ``eligibility`` decides whether
Source Diagnosis may be asked, and ``case_report`` / ``pair_report`` assemble
the two documents. Import from this package, not from its submodules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from llm4mtl.semantic_tests.failure_report.case_report import write_failure_report
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.models import DIFF_FIELDS
from llm4mtl.semantic_tests.failure_report.pair_report import write_pair_failure_report
from llm4mtl.semantic_tests.failure_report.request import (
    read_request_payload,
    request_type,
)

_WRITERS = {
    "test_case": write_failure_report,
    "execution_pair": write_pair_failure_report,
}


def write_report(
    payload: Mapping[str, Any],
    output: Path,
    *,
    scope: str,
) -> dict[str, Any]:
    """Assemble and persist the failure report of one ``scope``.

    The single entry point: a caller says which kind of failure it recorded and
    hands over the paths it recorded it from. Which request class validates the
    payload and which assembler builds the document is this package's business.

    Raises :class:`FailureReportError` for an unknown scope, a payload that does
    not satisfy the request boundary, or evidence that cannot form a
    trustworthy report.
    """
    request = request_type(scope).from_payload(payload)
    return _WRITERS[scope](request, output)


__all__ = [
    "DIFF_FIELDS",
    "FailureReportError",
    "read_request_payload",
    "write_report",
]
