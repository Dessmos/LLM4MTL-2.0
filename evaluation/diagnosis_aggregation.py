"""Group one execution attempt's diagnoses by the failure they are about.

Preparation writes one report per failing test case, and each report is
diagnosed on its own. That is right for the pipeline: each report is separate
evidence. But it over-counts faults. One broken model reference that fails three
test cases gives three reports and three verdicts, yet it is *one* defect.

So the raw records stay as written, and the grouping happens here, on read.
Reports are grouped by a fingerprint over what identifies a failure:

    failure_stage + exception type + normalized error summary
                  + top stack frame + transformation sha256

The error summary alone is not enough. It starts with the name of the first
failing test method, so one fault gives a different string per case;
normalization removes that prefix and the line numbers. And equal messages can
come from different places; the stack frame and the transformation hash keep
those apart.

Grouping never changes a verdict. Each cluster lists the verdicts its reports
received and how much they agree, which makes the consistency of Source
Diagnosis measurable.

It only reads recorded evidence and prints the result as JSON:

    PYTHONPATH=pipeline/src .venv/bin/python -m evaluation.diagnosis_aggregation \
      --batch batch_004 --run <run-id> [--attempt N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from llm4mtl.domain.diagnosis import aggregate_classifications
from llm4mtl.paths import TARGET
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.responses import recorded_diagnoses
from llm4mtl.semantic_tests.diagnosis_preparation import (
    DIAGNOSIS_DIRNAME,
    REPORT_CREATED,
    diagnosis_index_path,
)
from llm4mtl.semantic_tests.failure_report import CASE_SCOPE
from llm4mtl.serialization.json_io import read_json
from llm4mtl.vocabulary import EXECUTION_STAGE_ID

SCHEMA_VERSION = "1.0"
UNKNOWN = "unknown"
# The facets that identify a failure, in the order they enter its fingerprint.
FINGERPRINT_FACETS = (
    "failure_stage",
    "exception_type",
    "normalized_error_summary",
    "top_stack_frame",
    "transformation_sha256",
)
# ``methodThatFailedFirst: the real message``. Surefire does not write this
# prefix: ``surefire._describe`` adds it, and that text becomes the
# observation's ``error_summary``. The method changes per report; the fault
# does not.
METHOD_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*:\s+")
STACK_FRAME = re.compile(r"^\s*at\s+(?P<frame>\S+)", re.MULTILINE)
LINE_NUMBER = re.compile(r":\d+\b")
DIGITS = re.compile(r"\d+")
WHITESPACE = re.compile(r"\s+")


class DiagnosisAggregationError(ValueError):
    """Raised when an attempt's diagnosis evidence cannot be read."""


def aggregate_run_diagnoses(
    run_dir: Path, attempt: int, run_diagnoses: Path
) -> dict[str, Any]:
    """Cluster every prepared report of ``attempt`` and count what was diagnosed.

    ``run_diagnoses`` is the run's directory in the diagnoses area, resolved by
    the caller through the artifact layout.
    """
    run_dir = Path(run_dir).resolve()
    index_path = diagnosis_index_path(run_dir, attempt)
    if not index_path.is_file():
        raise DiagnosisAggregationError(
            f"run {run_dir.name} prepared no diagnosis evidence for attempt {attempt}"
        )
    index = read_json(index_path)
    verdicts = _recorded_verdicts(Path(run_diagnoses))

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
        "aggregate_verdict": aggregate_classifications(
            [cluster["verdict"] for pair in pairs for cluster in pair["clusters"]]
        ),
    }


def failure_fingerprint(report: dict[str, Any]) -> dict[str, Any]:
    """The identity of the failure one report is about, and its facets.

    The facets are returned beside the hash so a cluster can be read without
    re-opening the reports it was built from.
    """
    result = report.get("test_case_result") or report.get("pair_result") or {}
    facets = _failure_facets(result)
    identity = "\n".join(f"{key}={facets[key]}" for key in FINGERPRINT_FACETS)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return {"failure_fingerprint": digest, **facets}


def _failure_facets(result: dict[str, Any]) -> dict[str, str]:
    execution = result.get("execution") or {}
    observation = execution.get("observation") or {}
    error = execution.get("error") or {}
    failure = result.get("failure") or {}
    return {
        "failure_stage": str(observation.get("failure_stage") or UNKNOWN),
        "exception_type": _exception_type(error, failure),
        "normalized_error_summary": _normalize_summary(
            observation.get("error_summary") or failure.get("message") or ""
        ),
        "top_stack_frame": _top_frame(error.get("stack_traces") or []),
        "transformation_sha256": _transformation_sha256(result),
    }


def _exception_type(error: dict[str, Any], failure: dict[str, Any]) -> str:
    """The first line of the first recorded exception type.

    Surefire's `type` attribute is not always a bare class name: the ETL harness
    writes the message and the head of the trace into it. The first line is
    what identifies the exception either way.
    """
    exceptions = error.get("exceptions") or []
    recorded_type = exceptions[0].get("type") if exceptions else None
    return _first_line(recorded_type or failure.get("failure_type") or UNKNOWN)


def _transformation_sha256(result: dict[str, Any]) -> str:
    versions = result.get("versions") or {}
    transformation = versions.get("generated_transformation") or {}
    return str(transformation.get("sha256") or UNKNOWN)


def _aggregate_pair(
    run_dir: Path, pair: dict[str, Any], verdicts: dict[str, str]
) -> dict[str, Any]:
    reports = [
        entry
        for entry in pair.get("reports", [])
        if entry.get("status") == REPORT_CREATED and entry.get("report")
    ]
    clusters = _clusters(run_dir, reports, verdicts)
    affected = {case for cluster in clusters for case in cluster["test_cases"]}
    return {
        "pair_id": _pair_id(pair),
        "suite": pair.get("suite"),
        "transformation": pair.get("transformation"),
        "diagnosis_reports": len(reports),
        "affected_test_cases": len(affected),
        "unique_failure_clusters": len(clusters),
        "clusters": clusters,
        "aggregate_verdict": aggregate_classifications(
            [cluster["verdict"] for cluster in clusters]
        ),
    }


def _clusters(
    run_dir: Path, reports: list[dict[str, Any]], verdicts: dict[str, str]
) -> list[dict[str, Any]]:
    """Group the pair's reports by fingerprint, in the order they first appear."""
    clusters: dict[str, dict[str, Any]] = {}
    for entry in reports:
        reference = str(entry["report"])
        facets = failure_fingerprint(read_json(_report_path(run_dir, reference)))
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
        _add_report(cluster, entry, verdicts.get(_evidence_key(reference)))
    for cluster in clusters.values():
        cluster["diagnosed"] = len(cluster["classifications"])
        cluster["verdict"] = aggregate_classifications(cluster["classifications"])
        cluster["agreement"] = _agreement(cluster["classifications"])
    return list(clusters.values())


def _add_report(
    cluster: dict[str, Any], entry: dict[str, Any], verdict: str | None
) -> None:
    cluster["reports"] += 1
    scope = str(entry.get("scope") or CASE_SCOPE)
    if scope not in cluster["scopes"]:
        cluster["scopes"].append(scope)
    case = entry.get("test_case_id")
    if case is not None and case not in cluster["test_cases"]:
        cluster["test_cases"].append(case)
    if verdict is not None:
        cluster["classifications"].append(verdict)


def _totals(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    clusters = [cluster for pair in pairs for cluster in pair["clusters"]]
    diagnosed = sum(cluster["diagnosed"] for cluster in clusters)
    agreeing = sum(
        _majority_count(cluster["classifications"])
        for cluster in clusters
        if cluster["classifications"]
    )
    return {
        "execution_pairs": len(pairs),
        "diagnosis_reports": sum(pair["diagnosis_reports"] for pair in pairs),
        "unique_failure_clusters": len(clusters),
        "affected_test_cases": sum(pair["affected_test_cases"] for pair in pairs),
        "diagnosed": diagnosed,
        # How often the separate diagnoses of one failure agreed. Null, not
        # 1.0, when nothing was diagnosed: no verdicts is not perfect agreement.
        "agreement": round(agreeing / diagnosed, 4) if diagnosed else None,
    }


def _agreement(classifications: list[str]) -> float | None:
    if not classifications:
        return None
    return round(_majority_count(classifications) / len(classifications), 4)


def _majority_count(classifications: list[str]) -> int:
    """How many of the classifications agree with the most common one."""
    return Counter(classifications).most_common(1)[0][1]


def _recorded_verdicts(run_diagnoses: Path) -> dict[str, str]:
    """Every persisted verdict of this run, keyed by the report it diagnosed."""
    verdicts: dict[str, str] = {}
    for record in recorded_diagnoses(run_diagnoses):
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
    marker = f"/{DIAGNOSIS_DIRNAME}/"
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


def latest_execution_attempt(run_dir: Path) -> int:
    """The highest execution attempt the run recorded."""
    attempts_dir = RunPaths(Path(run_dir)).stage_attempts_dir(EXECUTION_STAGE_ID)
    attempts = existing_attempts(attempts_dir)
    if not attempts:
        raise DiagnosisAggregationError(
            f"run {Path(run_dir).name} recorded no execution attempt"
        )
    return max(attempts)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True, help="batch id the run belongs to")
    parser.add_argument("--run", required=True, help="run id")
    parser.add_argument(
        "--attempt",
        type=int,
        help="execution attempt to aggregate; defaults to the latest recorded one",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = TARGET.run_dir(args.batch, args.run)
    try:
        attempt = args.attempt
        if attempt is None:
            attempt = latest_execution_attempt(run_dir)
        aggregated = aggregate_run_diagnoses(
            run_dir, attempt, TARGET.run_diagnoses_dir(args.batch, args.run)
        )
    except DiagnosisAggregationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(aggregated, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
