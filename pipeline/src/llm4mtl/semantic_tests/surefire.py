"""Read which harness phase failed from the Surefire XML reports.

JUnit separates a ``<failure>`` (an assertion did not hold) from an ``<error>``
(the test threw before it could judge anything). That is the difference between
"the generated oracle disagrees with the reference" and "the generated test
could not run". Maven's console output loses it: both print as
``Tests run: N, Failures: F, Errors: E``.

Every marker below was copied from a real report, never guessed. The ETL
markers come from the phase-probe report in ``pipeline/tests/fixtures/surefire/``.
The other engines' markers come from the recorded 2026-07-30/31 ATL, QVT-O, and
Reactions runs.

An error that matches no marker is ``unclassified_runtime``, NOT a phase.
Guessing a phase would blame either the suite or the transformation, and this
evidence supports neither. Such a run reaches no oracle verdict, so it counts in
neither the reference-pass nor the reference-fail population.

Add a marker only when the string identifies the phase on its own. Two known
messages stay unclassified for that reason:
``java.lang.String cannot be cast to java.util.Collection`` (Reactions) can come
from the harness or the engine, and ``Type 'Source!Tree' not found`` (ETL) can
be an unregistered model or a real type error in the transformation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from llm4mtl.domain.observations import FailureStage

# An error raised while loading a model: the engine never ran.
#
# ``org.eclipse.emf.ecore.xmi.`` is the EMF XMI (de)serialization package, so
# every exception it raises happened while reading or writing a model resource.
# It covers PackageNotFoundException, ClassNotFoundException,
# FeatureNotFoundException, and IllegalValueException, all observed in the ATL
# and QVT-O runs.
MODEL_LOADING_MARKERS = (
    "Resource not found",
    "EolModelLoadingException",
    "ModelLoadingException",
    "Could not load model",
    "org.eclipse.emf.ecore.xmi.",
    "Cannot create a resource for",
    "Cannot find reference model",
    "Could not find model",
)

# An error raised by the transformation engine itself while executing.
#
# The package prefixes name exactly one engine each, so they cannot be
# ambiguous. The literal messages were observed in the Reactions and ATL runs:
# Vitruv fails change propagation with "Cannot identify the packages of this
# change" / "dangling object", and the ATL VM with "Operation not found:".
ENGINE_RUNTIME_MARKERS = (
    "org.eclipse.epsilon",
    "EolRuntimeException",
    "EolTypeNotFound",
    "org.eclipse.m2m.atl",
    "org.eclipse.m2m.qvt.oml",
    "tools.vitruv",
    "Cannot identify the packages of this change",
    "dangling object",
    "Operation not found:",
)

TRANSFORMATION_PARSE_MARKERS = (
    "ETL parse errors",
    "ParseProblem",
    "Compilation errors found in unit",
)

# Where Maven writes the reports, relative to the Maven project directory.
SUREFIRE_REPORTS_DIR = Path("target") / "surefire-reports"
# The file name pattern of one Surefire XML report.
REPORT_FILE_GLOB = "TEST-*.xml"
# A longer report message is cut to this many characters.
MAX_MESSAGE_CHARS = 500


@dataclass(frozen=True)
class SurefireReport:
    """The parts of a Surefire run that identify which phase failed."""

    tests: int
    failures: int
    errors: int
    error_messages: tuple[str, ...] = ()
    failure_messages: tuple[str, ...] = ()

    @property
    def first_error(self) -> str:
        return self.error_messages[0] if self.error_messages else ""

    @property
    def first_failure(self) -> str:
        return self.failure_messages[0] if self.failure_messages else ""

    def failure_stage(self) -> str:
        """Which phase this run failed in, or ``""`` when nothing failed.

        Errors are checked before failures: a run that both threw and failed an
        assertion never reached a trustworthy verdict, so the throw decides.

        An error no marker recognizes yields ``unclassified_runtime``. That says
        the evidence is unclear. It blames neither the suite nor the
        transformation.
        """
        if self.errors:
            joined = " ".join(self.error_messages)
            if _contains(joined, TRANSFORMATION_PARSE_MARKERS):
                return FailureStage.TRANSFORMATION_PARSE
            if _contains(joined, MODEL_LOADING_MARKERS):
                return FailureStage.MODEL_LOADING
            if _contains(joined, ENGINE_RUNTIME_MARKERS):
                return FailureStage.ENGINE_RUNTIME
            return FailureStage.UNCLASSIFIED_RUNTIME
        if self.failures:
            if _contains(
                " ".join(self.failure_messages), TRANSFORMATION_PARSE_MARKERS
            ):
                return FailureStage.TRANSFORMATION_PARSE
            return FailureStage.ASSERTION_FAILURE
        return ""


def read_surefire_reports(reports_dir: Path) -> SurefireReport | None:
    """Add up the Surefire XML reports of one run, or ``None`` when absent.

    ``None`` means "no readable report exists". Only then may the caller fall
    back to the console. A report that parsed and counted zero tests is NOT that
    state: it proves nothing ran, and the caller must treat it as a
    test-discovery failure. The console fallback would read exit code 0 as
    success.
    """
    report_roots = _parsed_report_roots(reports_dir)
    if not report_roots:
        # No report file, or every one was malformed: there is no readable XML
        # evidence.
        return None
    return _aggregate(report_roots)


def _parsed_report_roots(reports_dir: Path) -> list[ET.Element]:
    """Parse every report file of one run, in file-name order."""
    if not reports_dir.is_dir():
        return []
    roots: list[ET.Element] = []
    for path in sorted(reports_dir.glob(REPORT_FILE_GLOB)):
        try:
            roots.append(ET.parse(path).getroot())
        except ET.ParseError:
            # A malformed report says nothing; the console fallback decides.
            continue
    return roots


def _aggregate(report_roots: list[ET.Element]) -> SurefireReport:
    """Add up the counts and messages of all parsed reports of one run."""
    error_messages: list[str] = []
    failure_messages: list[str] = []
    for root in report_roots:
        report_errors, report_failures = _report_messages(root)
        error_messages.extend(report_errors)
        failure_messages.extend(report_failures)
    return SurefireReport(
        tests=sum(_count(root, "tests") for root in report_roots),
        failures=sum(_count(root, "failures") for root in report_roots),
        errors=sum(_count(root, "errors") for root in report_roots),
        error_messages=tuple(error_messages),
        failure_messages=tuple(failure_messages),
    )


def testcase_method_name(case_name: str) -> str:
    """The Java method a ``<testcase name="...">`` names, without its parameters.

    Surefire writes a JUnit 5 method that takes parameters with their types,
    for example ``createsMale(Path)`` for a test that receives a ``@TempDir``.
    The Reactions harness does that; the other harnesses' methods take none.
    """
    return case_name.split("(", 1)[0]


def testcase_outcome(case: ET.Element) -> tuple[str, ET.Element | None]:
    """The outcome of one ``<testcase>``: ``passed``, ``failed``, or ``error``.

    An ``<error>`` wins over a ``<failure>``. A case that both threw and lost an
    assertion never reached a trustworthy verdict, so the throw decides; the
    assertion result is no longer reliable.

    The failure-report views and diagnosis preparation all use this function,
    and ``SurefireReport.failure_stage`` uses the same order, so they cannot
    disagree about one recorded case.
    """
    error = case.find("error")
    if error is not None:
        return "error", error
    failure = case.find("failure")
    if failure is not None:
        return "failed", failure
    return "passed", None


def _report_messages(root: ET.Element) -> tuple[list[str], list[str]]:
    """Collect error and failure descriptions in test-case document order."""
    error_messages: list[str] = []
    failure_messages: list[str] = []
    for case in root.iter("testcase"):
        error_messages.extend(_describe(case, node) for node in case.findall("error"))
        failure_messages.extend(
            _describe(case, node) for node in case.findall("failure")
        )
    return error_messages, failure_messages


def _count(root: ET.Element, attribute: str) -> int:
    try:
        return int(root.get(attribute, "0"))
    except ValueError:
        return 0


def _describe(case: ET.Element, node: ET.Element) -> str:
    message = (node.get("message") or node.get("type") or "").strip()
    return f"{case.get('name', '?')}: {message}"[:MAX_MESSAGE_CHARS]


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)
