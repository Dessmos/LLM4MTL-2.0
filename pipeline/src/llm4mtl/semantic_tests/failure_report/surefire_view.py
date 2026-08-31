"""Projections of the archived Surefire reports into report evidence.

The case view answers "what happened to this one test method"; the pair view
answers "what did the reports say about a run that named no test method". Both
read the same parsed cases, so the two report types cannot disagree about which
outcome a case had.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Sequence

from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_method_name
from llm4mtl.semantic_tests.failure_report.artifacts import _repository_path
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.models import (
    ASSERTION_OUTCOME_PREFIX,
    ASSERTION_OUTCOME_SEPARATOR,
    SYSTEM_ERR_EXCERPT_CHARS,
)
from llm4mtl.semantic_tests.surefire import testcase_outcome


def _surefire_evidence(
    report_paths: Sequence[Path], test_case_id: str
) -> dict[str, Any]:
    method_name = sanitize_method_name(test_case_id)
    test_cases: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    for path, case in _matching_surefire_cases(report_paths, method_name):
        test_case, exception, trace = _surefire_test_case(path, case)
        test_cases.append(test_case)
        if exception is not None:
            exceptions.append(exception)
        if trace:
            stack_traces.append(trace)
    return {
        "test_cases": test_cases,
        "exceptions": exceptions,
        "stack_traces": stack_traces,
    }


def _matching_surefire_cases(
    report_paths: Sequence[Path], method_name: str
) -> Iterator[tuple[Path, ET.Element]]:
    """Yield matching test cases in report and XML document order."""
    for path in report_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            raise FailureReportError(f"invalid Surefire report {path}: {exc}") from exc
        for case in root.iter("testcase"):
            if case.get("name") == method_name:
                yield path, case


def _surefire_test_case(
    path: Path, case: ET.Element
) -> tuple[dict[str, Any], dict[str, str] | None, str]:
    status, node = testcase_outcome(case)
    message = str(node.get("message") or "") if node is not None else ""
    expected, actual = _assertion_outcome(message)
    test_case = {
        "report": _repository_path(path),
        "test_class": case.get("classname"),
        "test_method": case.get("name"),
        "duration_seconds": case.get("time"),
        "status": status,
        "failure_type": (
            str(node.get("type") or node.tag) if node is not None else None
        ),
        "message": message or None,
        "expected": expected,
        "actual": actual,
    }
    if node is None:
        return test_case, None, ""
    exception = {
        "type": str(node.get("type") or node.tag),
        "message": message,
    }
    return test_case, exception, (node.text or "").strip()


def _assertion_outcome(message: str) -> tuple[str | None, str | None]:
    """The expected and actual values JUnit printed, or ``(None, None)``.

    Extraction is deliberately literal. When the message is not exactly the
    ``expected: <X> but was: <Y>`` shape the pair is unknown, and an unknown
    actual result is reported as unknown: the raw message and the archived
    report stay in the evidence, and the diagnosis LLM is never handed a value
    this module reconstructed.
    """
    prefix_at = message.find(ASSERTION_OUTCOME_PREFIX)
    separator_at = message.rfind(ASSERTION_OUTCOME_SEPARATOR)
    if prefix_at < 0 or separator_at < prefix_at or not message.rstrip().endswith(">"):
        return None, None
    expected = message[prefix_at + len(ASSERTION_OUTCOME_PREFIX) : separator_at]
    if not expected.endswith(">"):
        return None, None
    actual = message.rstrip()[separator_at + len(ASSERTION_OUTCOME_SEPARATOR) : -1]
    return expected[:-1], actual


def _recorded_failure_view(surefire_evidence: dict[str, Any]) -> dict[str, Any] | None:
    """The one recorded failure this report is about, if there is one.

    Both JUnit outcomes qualify and are kept apart by ``kind``: a ``failure`` is
    an assertion that was evaluated and did not hold, an ``error`` is a throw
    before any verdict. The second is still a real failure of the pairing — it
    is what a broken generated transformation usually produces — so it gets a
    report, with the exception and stack trace as its evidence and no invented
    expected/actual.

    ``None`` when the reports name no failure for the selected test method, or
    name more than one: neither state identifies a single failure, and picking
    one would be a choice this module has no evidence for.
    """
    failures = [
        case
        for case in surefire_evidence["test_cases"]
        if case.get("status") in {"failed", "error"}
    ]
    if len(failures) != 1:
        return None
    failure = failures[0]
    return {
        "kind": (
            "assertion_failure"
            if failure.get("status") == "failed"
            else "runtime_error"
        ),
        "report": failure.get("report"),
        "test_class": failure.get("test_class"),
        "test_method": failure.get("test_method"),
        "failure_type": failure.get("failure_type"),
        "message": failure.get("message"),
        "expected": failure.get("expected"),
        "actual": failure.get("actual"),
        "extraction": (
            "junit_assertion_message"
            if failure.get("expected") is not None or failure.get("actual") is not None
            else "unavailable"
        ),
    }


def _pair_surefire_evidence(report_paths: Sequence[Path]) -> dict[str, Any]:
    """What the archived reports say about a run with no per-test failure.

    ``test_failures`` is the proof that no narrower attribution exists: it lists
    every test method the reports *did* mark, so a caller can see that the
    pair-level report was not used to bypass a per-case one. The exceptions come
    from the testsuite element itself, which is where a harness that died before
    running a test writes them.
    """
    test_failures: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    system_err: list[str] = []
    reports: list[str] = []
    for path in report_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        reports.append(_repository_path(path))
        test_failures.extend(_pair_test_failures(root))
        report_exceptions, report_traces = _suite_failures(root)
        exceptions.extend(report_exceptions)
        stack_traces.extend(report_traces)
        system_err.extend(_system_err_excerpts(root))
    return {
        "test_failures": test_failures,
        "exceptions": exceptions,
        "stack_traces": stack_traces,
        "system_err": system_err,
        "reports": reports,
        "failure_type": exceptions[0]["type"] if exceptions else None,
        "message": exceptions[0]["message"] if exceptions else "",
    }


def _pair_test_failures(root: ET.Element) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for case in root.iter("testcase"):
        status, node = testcase_outcome(case)
        if node is None:
            continue
        failures.append(
            {
                "test_class": case.get("classname"),
                "test_method": case.get("name"),
                "status": status,
            }
        )
    return failures


def _suite_failures(
    root: ET.Element,
) -> tuple[list[dict[str, str]], list[str]]:
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    for node in [*root.findall("error"), *root.findall("failure")]:
        exceptions.append(
            {
                "type": str(node.get("type") or node.tag),
                "message": str(node.get("message") or ""),
            }
        )
        trace = (node.text or "").strip()
        if trace:
            stack_traces.append(trace)
    return exceptions, stack_traces


def _system_err_excerpts(root: ET.Element) -> list[str]:
    excerpts: list[str] = []
    for stream in root.findall("system-err"):
        text = (stream.text or "").strip()
        if text:
            excerpts.append(text[-SYSTEM_ERR_EXCERPT_CHARS:])
    return excerpts
