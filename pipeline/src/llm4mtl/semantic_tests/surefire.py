"""Read which harness phase failed out of the Surefire reports.

JUnit separates a ``<failure>`` (an assertion did not hold) from an ``<error>``
(the test threw before it could judge anything). That distinction is the whole
difference between "the generated oracle disagrees with the reference" and "the
generated test could not run", and Maven's console output does not carry it:
both print as ``Tests run: N, Failures: F, Errors: E``.

Every marker below was taken from a real report, never guessed. The original
set came from the ETL harness (see
``pipeline/tests/fixtures/surefire/phase-probe.xml``);
the per-engine markers were read off the recorded observations of the
2026-07-30/31 ATL, QVT-O, and Reactions runs under ``artifacts/work/runs/``.

An error that matches no marker is reported as ``unclassified_runtime`` and NOT
as a phase. Guessing a phase would attribute the failure either to the suite or
to the transformation, and both are claims this evidence cannot support; the
funnel counts these separately as inconclusive so neither the pass nor the fail
population absorbs them.

Add a marker only when the string identifies the phase on its own. Two known
messages are deliberately left unclassified because they do not:
``java.lang.String cannot be cast to java.util.Collection`` (Reactions) could
come from the harness or the engine, and ``Type 'Source!Tree' not found`` (ETL)
could be an unregistered model or a genuine type error in the transformation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

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

TRANSFORMATION_PARSE_MARKERS = ("ETL parse errors", "ParseProblem")

# The error threw, but nothing in it identifies which phase. Never a phase claim.
UNCLASSIFIED_RUNTIME = "unclassified_runtime"


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
        assertion never reached a trustworthy verdict, so the throw is what the
        observation is about.

        An error no marker recognizes yields ``unclassified_runtime``. That is a
        statement about the evidence, not about the suite or the transformation,
        and every consumer must keep it out of both verdict populations.
        """
        if self.errors:
            joined = " ".join(self.error_messages)
            if _contains(joined, TRANSFORMATION_PARSE_MARKERS):
                return "transformation_parse"
            if _contains(joined, MODEL_LOADING_MARKERS):
                return "model_loading"
            if _contains(joined, ENGINE_RUNTIME_MARKERS):
                return "engine_runtime"
            return UNCLASSIFIED_RUNTIME
        return "assertion_failure" if self.failures else ""


def read_surefire_reports(reports_dir: Path) -> SurefireReport | None:
    """Aggregate the Surefire XML reports of one run, or ``None`` when absent.

    ``None`` means "no readable report exists", which is the only state the
    console fallback may be used for. A report that parsed and recorded zero
    tests is NOT that state: it is positive evidence that nothing ran, and the
    caller must treat it as a test-discovery failure rather than fall back to a
    console summary that would read an exit code of 0 as success.
    """
    if not reports_dir.is_dir():
        return None
    report_files = sorted(reports_dir.glob("TEST-*.xml"))
    if not report_files:
        return None

    parsed = 0
    tests = failures = errors = 0
    error_messages: list[str] = []
    failure_messages: list[str] = []
    for path in report_files:
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            # A malformed report says nothing; the console fallback decides.
            continue
        parsed += 1
        tests += _count(root, "tests")
        failures += _count(root, "failures")
        errors += _count(root, "errors")
        for case in root.iter("testcase"):
            for node in case.findall("error"):
                error_messages.append(_describe(case, node))
            for node in case.findall("failure"):
                failure_messages.append(_describe(case, node))

    if not parsed:
        # Every report file was malformed: there is no readable XML evidence.
        return None

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
