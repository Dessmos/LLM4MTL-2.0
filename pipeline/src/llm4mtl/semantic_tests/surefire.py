"""Read which harness phase failed out of the Surefire reports.

JUnit separates a ``<failure>`` (an assertion did not hold) from an ``<error>``
(the test threw before it could judge anything). That distinction is the whole
difference between "the generated oracle disagrees with the reference" and "the
generated test could not run", and Maven's console output does not carry it:
both print as ``Tests run: N, Failures: F, Errors: E``.

The markers below were taken from real reports produced by the ETL harness
(see ``pipeline/tests/fixtures/surefire/phase-probe.xml``), not guessed:

* a missing input model surfaces as ``IllegalArgumentException: Resource not found``
  from the harness's own resource lookup;
* driving the engine wrongly surfaces as an Epsilon exception, whose ``type``
  attribute is the Epsilon message rather than a class name.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# An error raised while loading a model: the engine never ran.
MODEL_LOADING_MARKERS = (
    "Resource not found",
    "EolModelLoadingException",
    "ModelLoadingException",
    "Could not load model",
)

# An error raised by the transformation engine itself while executing.
ENGINE_RUNTIME_MARKERS = (
    "org.eclipse.epsilon",
    "EolRuntimeException",
    "EolTypeNotFound",
)

TRANSFORMATION_PARSE_MARKERS = ("ETL parse errors", "ParseProblem")


@dataclass(frozen=True)
class SurefireReport:
    """The parts of a Surefire run that identify which phase failed."""

    tests: int
    failures: int
    errors: int
    error_messages: tuple[str, ...] = ()
    failure_messages: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return self.tests == 0 and self.failures == 0 and self.errors == 0

    @property
    def first_error(self) -> str:
        return self.error_messages[0] if self.error_messages else ""

    @property
    def first_failure(self) -> str:
        return self.failure_messages[0] if self.failure_messages else ""

    def failure_stage(self) -> str:
        """Which phase this run failed in, or ``""`` when nothing failed.

        Errors are checked before failures: a run that both threw and failed an
        assertion never reached a trustworthy verdict, so the throw is what the
        observation is about.
        """
        if self.errors:
            joined = " ".join(self.error_messages)
            if _contains(joined, TRANSFORMATION_PARSE_MARKERS):
                return "transformation_parse"
            if _contains(joined, MODEL_LOADING_MARKERS):
                return "model_loading"
            if _contains(joined, ENGINE_RUNTIME_MARKERS):
                return "engine_runtime"
            return "test_runtime"
        return "assertion_failure" if self.failures else ""


def read_surefire_reports(reports_dir: Path) -> SurefireReport | None:
    """Aggregate the Surefire XML reports of one run, or ``None`` when absent."""
    if not reports_dir.is_dir():
        return None
    report_files = sorted(reports_dir.glob("TEST-*.xml"))
    if not report_files:
        return None

    tests = failures = errors = 0
    error_messages: list[str] = []
    failure_messages: list[str] = []
    for path in report_files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            # A malformed report says nothing; the console fallback decides.
            continue
        tests += _count(root, "tests")
        failures += _count(root, "failures")
        errors += _count(root, "errors")
        for case in root.iter("testcase"):
            for node in case.findall("error"):
                error_messages.append(_describe(case, node))
            for node in case.findall("failure"):
                failure_messages.append(_describe(case, node))

    return SurefireReport(
        tests=tests,
        failures=failures,
        errors=errors,
        error_messages=tuple(error_messages),
        failure_messages=tuple(failure_messages),
    )


def _count(root: ET.Element, attribute: str) -> int:
    try:
        return int(root.get(attribute, "0"))
    except ValueError:
        return 0


def _describe(case: ET.Element, node: ET.Element) -> str:
    message = (node.get("message") or node.get("type") or "").strip()
    return f"{case.get('name', '?')}: {message}"[:500]


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)
