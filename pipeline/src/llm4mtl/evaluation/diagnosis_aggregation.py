"""Cluster one execution attempt's diagnoses by the failure they are about.

Preparation attaches one report to every failing test case, and the diagnosis
subworkflow diagnoses each of them. That is right for the pipeline: each report
is a separate observation, made from separate evidence, and dropping any of them
would decide on part of the evidence. It is wrong for a sentence in a thesis. A
run with one generated transformation, one execution and one broken model
reference produces three reports and three verdicts — but it observed *one*
defect affecting three test cases, and "Source Diagnosis detected three
transformation defects" would count the same fault three times.

So the raw records stay exactly as the pipeline wrote them, and the counting
happens here, on read. Reports are grouped by a fingerprint over what actually
identifies a failure:

    failure_stage + exception type + normalized error summary
                  + top stack frame + transformation sha256

Not the error summary alone. The same message legitimately arises from different
places, and — in the other direction — the summary carries the test method that
hit it first, so three cases failing on one broken type reference produce three
different strings for one fault. Normalization strips that prefix and the line
numbers; the stack frame and the transformation hash are what keep two textually
equal messages from different places apart.

Clustering never changes a verdict. Each cluster reports the classifications its
reports received and how far they agreed, which is what makes the consistency of
Source Diagnosis measurable instead of assumed.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from llm4mtl.serialization.json_io import read_json

SCHEMA_VERSION = "1.0"
DIAGNOSIS_FILENAME = "diagnosis.json"
INDEX_FILENAME = "index.json"
UNKNOWN = "unknown"
# ``methodThatFailedFirst: the real message``. Surefire names the method that
# reached the fault first, so the prefix varies per report while the fault does
# not.
METHOD_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:\s+")
STACK_FRAME = re.compile(r"^\s*at\s+(?P<frame>\S+)", re.MULTILINE)
LINE_NUMBER = re.compile(r":\d+\b")
DIGITS = re.compile(r"\d+")
WHITESPACE = re.compile(r"\s+")


class DiagnosisAggregationError(ValueError):
    """Raised when an attempt's diagnosis evidence cannot be read."""


def aggregate_run_diagnoses(
    run_dir: Path, attempt: int, diagnoses_root: Path
) -> dict[str, Any]:
    """Cluster every prepared report of ``attempt`` and count what was diagnosed."""
    run_dir = Path(run_dir).resolve()
    index_path = (
        run_dir / "diagnosis" / "execution" / f"attempt-{attempt:03d}" / INDEX_FILENAME
    )
    if not index_path.is_file():
        raise DiagnosisAggregationError(
            f"run {run_dir.name} prepared no diagnosis evidence for attempt {attempt}"
        )
    index = read_json(index_path)
    verdicts = _recorded_verdicts(Path(diagnoses_root) / run_dir.name)

    pairs = [
        _aggregate_pair(run_dir, pair, verdicts) for pair in index.get("pairs", [])
    ]
    totals = _totals(pairs)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": index.get("run_id", run_dir.name),
        "attempt": index.get("attempt", attempt),
        "pairs": pairs,
        "totals": totals,
        "aggregate_verdict": aggregate_verdict(
            [cluster["verdict"] for pair in pairs for cluster in pair["clusters"]]
        ),
    }


def aggregate_verdict(verdicts: Iterable[str | None]) -> str | None:
    """The conservative aggregate the pipeline routes on, over any set of verdicts."""
    present = [verdict for verdict in verdicts if verdict]
    if not present:
        return None
    if "AMBIGUOUS" in present:
        return "AMBIGUOUS"
    has_transformation = "TRANSFORMATION_DEFECT" in present
    has_test = "TEST_DEFECT" in present
    if has_transformation and has_test:
        return "AMBIGUOUS"
    return "TRANSFORMATION_DEFECT" if has_transformation else "TEST_DEFECT"


def failure_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    """The identity of the failure one report is about, and its facets.

    The facets are returned beside the hash so a cluster can be read without
    re-opening the reports it was built from.
    """
    result = report.get("test_case_result") or report.get("pair_result") or {}
    observation = (result.get("execution") or {}).get("observation") or {}
    error = (result.get("execution") or {}).get("error") or {}
    exceptions = error.get("exceptions") or []
    failure = result.get("failure") or {}
    facets = {
        "failure_stage": str(observation.get("failure_stage") or UNKNOWN),
        # Surefire's `type` attribute is not always a bare class name: the ETL
        # harness writes the message and the head of the trace into it. The
        # first line is what identifies the exception either way.
        "exception_type": _first_line(
            (exceptions[0].get("type") if exceptions else None)
            or failure.get("failure_type")
            or UNKNOWN
        ),
        "normalized_error_summary": _normalize_summary(
            observation.get("error_summary") or failure.get("message") or ""
        ),
        "top_stack_frame": _top_frame(error.get("stack_traces") or []),
        "transformation_sha256": str(
            ((result.get("versions") or {}).get("generated_transformation") or {}).get(
                "sha256"
            )
            or UNKNOWN
        ),
    }
    digest = hashlib.sha256(
        "\n".join(
            f"{key}={facets[key]}"
            for key in (
                "failure_stage",
                "exception_type",
                "normalized_error_summary",
                "top_stack_frame",
                "transformation_sha256",
            )
        ).encode("utf-8")
    ).hexdigest()
    return {"failure_fingerprint": digest, **facets}


def _aggregate_pair(
    run_dir: Path, pair: dict[str, Any], verdicts: dict[str, str]
) -> dict[str, Any]:
    clusters: dict[str, dict[str, Any]] = {}
    reports = [
        entry
        for entry in pair.get("reports", [])
        if entry.get("status") == "created" and entry.get("report")
    ]
    for entry in reports:
        report = read_json(_report_path(run_dir, str(entry["report"])))
        facets = failure_fingerprint(report)
        cluster = clusters.setdefault(
            facets["failure_fingerprint"],
            {
                **facets,
                "reports": 0,
                "scopes": [],
                "test_cases": [],
                "classifications": [],
            },
        )
        cluster["reports"] += 1
        scope = str(entry.get("scope") or "test_case")
        if scope not in cluster["scopes"]:
            cluster["scopes"].append(scope)
        case = entry.get("test_case_id")
        if case is not None and case not in cluster["test_cases"]:
            cluster["test_cases"].append(case)
        verdict = verdicts.get(_evidence_key(str(entry["report"])))
        if verdict is not None:
            cluster["classifications"].append(verdict)

    for cluster in clusters.values():
        cluster["diagnosed"] = len(cluster["classifications"])
        cluster["verdict"] = aggregate_verdict(cluster["classifications"])
        cluster["agreement"] = _agreement(cluster["classifications"])

    ordered = list(clusters.values())
    affected = {
        case for cluster in ordered for case in cluster["test_cases"]
    }
    return {
        "pair_id": _pair_id(pair),
        "suite": pair.get("suite"),
        "transformation": pair.get("transformation"),
        "diagnosis_reports": len(reports),
        "affected_test_cases": len(affected),
        "unique_failure_clusters": len(ordered),
        "clusters": ordered,
        "aggregate_verdict": aggregate_verdict(
            [cluster["verdict"] for cluster in ordered]
        ),
    }


def _totals(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = [cluster for pair in pairs for cluster in pair["clusters"]]
    diagnosed = sum(cluster["diagnosed"] for cluster in clusters)
    agreeing = sum(
        Counter(cluster["classifications"]).most_common(1)[0][1]
        for cluster in clusters
        if cluster["classifications"]
    )
    return {
        "execution_pairs": len(pairs),
        "diagnosis_reports": sum(pair["diagnosis_reports"] for pair in pairs),
        "unique_failure_clusters": len(clusters),
        "affected_test_cases": sum(pair["affected_test_cases"] for pair in pairs),
        "diagnosed": diagnosed,
        # How often the separate diagnoses of one failure agreed with each other.
        # Null rather than 1.0 when nothing was diagnosed: unanimity among no
        # verdicts is not perfect consistency.
        "agreement": round(agreeing / diagnosed, 4) if diagnosed else None,
    }


def _agreement(classifications: list[str]) -> float | None:
    if not classifications:
        return None
    majority = Counter(classifications).most_common(1)[0][1]
    return round(majority / len(classifications), 4)


def _recorded_verdicts(run_diagnoses: Path) -> dict[str, str]:
    """Every persisted verdict of this run, keyed by the report it diagnosed."""
    verdicts: dict[str, str] = {}
    if not run_diagnoses.is_dir():
        return verdicts
    for attempt_dir in sorted(run_diagnoses.glob("attempt-*")):
        record = attempt_dir / DIAGNOSIS_FILENAME
        if not record.is_file():
            continue
        diagnosis = read_json(record)
        reference = diagnosis.get("evidence_ref")
        if reference:
            verdicts[_evidence_key(str(reference))] = str(diagnosis["classification"])
    return verdicts


def _evidence_key(reference: str) -> str:
    """A report path as both writers spell it: the part below the run directory.

    The index cites reports repository-relative; a diagnosis record cites the
    same file relative to its run. Comparing the shared tail matches them without
    either side having to know the other's base.
    """
    normalized = reference.replace("\\", "/")
    marker = "/diagnosis/"
    if marker in normalized:
        return normalized[normalized.index(marker) + 1 :]
    return normalized.lstrip("/")


def _report_path(run_dir: Path, reference: str) -> Path:
    key = _evidence_key(reference)
    candidate = run_dir / key
    if candidate.is_file():
        return candidate
    raise DiagnosisAggregationError(f"prepared report is missing: {reference}")


def _pair_id(pair: dict[str, Any]) -> str:
    suite = Path(str(pair.get("suite") or UNKNOWN)).name
    transformation = Path(str(pair.get("transformation") or UNKNOWN)).name
    return f"{suite}::{transformation}"


def _normalize_summary(summary: object) -> str:
    """The message without what varies between reports of the same failure."""
    text = WHITESPACE.sub(" ", str(summary)).strip()
    text = METHOD_PREFIX.sub("", text)
    return LINE_NUMBER.sub(":#", text)


def _first_line(value: object) -> str:
    """The first non-empty line, without line numbers that shift per build."""
    for line in str(value).splitlines():
        stripped = WHITESPACE.sub(" ", line).strip()
        if stripped:
            return LINE_NUMBER.sub(":#", stripped)
    return UNKNOWN


def _top_frame(stack_traces: list[Any]) -> str:
    for trace in stack_traces:
        match = STACK_FRAME.search(str(trace))
        if match:
            return DIGITS.sub("#", match.group("frame"))
    return UNKNOWN
