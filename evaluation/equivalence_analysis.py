"""Recover supplementary PPL and audit mutation-equivalence evidence."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from evaluation._common import portable, repository_path
from evaluation.legacy_campaign.protocol import behavioral_outcome
from evaluation.legacy_pilot.assessment import sha256
from evaluation.legacy_pilot.run_pilot import write_csv, write_json
from evaluation.mutation.equivalence_probes import is_counterexample
from llm4mtl.paths import REPO_ROOT, TARGET


# Inputs, relative to the repository. Change them here to analyse other
# reductions or another frozen legacy campaign.
LEGACY_EVALUATION_ROOT = TARGET.artifacts / "legacy-suite-evaluation"
RQ_SUMMARY_DIR = LEGACY_EVALUATION_ROOT / "rq-summary-20261012-v1"
CAMPAIGN_DIR = LEGACY_EVALUATION_ROOT / "campaign-20261008-v1"
CAMPAIGN_REPORT_DIR = CAMPAIGN_DIR / "report-v3"
CAMPAIGN_RAW_DIR = CAMPAIGN_DIR / "raw"
# The candidate LoC definition is taken from the archived copy that produced
# the frozen tables, not from the live evaluation.reduce_tables.
LOC_DEFINITION = LEGACY_EVALUATION_ROOT / "tables-20261009-v1" / "reduce_tables.py"
MUTANT_CATALOG = REPO_ROOT / "evaluation" / "mutants" / "manifest.json"
MUTANTS_DIR = REPO_ROOT / "evaluation" / "mutants"


@dataclass(frozen=True)
class CountRecovery:
    count: int | None
    basis: str


@dataclass(frozen=True)
class ScoreInterval:
    killed: int
    known_non_equivalent: int
    unresolved: int
    lower: float | None
    upper: float | None
    exact: float | None


def mutation_interval(killed: int, known_non_equivalent: int, unresolved: int) -> ScoreInterval:
    """Bound a score with fixed kills and an uncertain non-equivalent denominator."""
    if min(killed, known_non_equivalent, unresolved) < 0 or killed > known_non_equivalent:
        raise ValueError("inconsistent mutation score population")
    maximum = known_non_equivalent + unresolved
    lower = killed / maximum if maximum else None
    upper = killed / known_non_equivalent if known_non_equivalent else (0.0 if maximum else None)
    exact = lower if unresolved == 0 else None
    return ScoreInterval(killed, known_non_equivalent, unresolved, lower, upper, exact)


def recover_etl_count(parsed: bool, diagnostic: str, measured: int | None = None) -> CountRecovery:
    """Recover counts without interpreting a parser exception as a parse problem.

The pass inference is conditional on the archived ETL driver contract verified
by the caller. Each normal diagnostic line represents one emitted ParseProblem.
"""
    if measured is not None:
        if measured < 0:
            return CountRecovery(None, "PARSER_TECHNICAL_FAILURE")
        if parsed and measured != 0:
            raise ValueError("ETL driver pass conflicts with its measured count")
        return CountRecovery(measured, "MEASURED_CSV")
    if parsed:
        return CountRecovery(0, "INFERRED_FROM_ARCHIVED_DRIVER_PASS_CONTRACT")
    lines = diagnostic.splitlines()
    if lines and all(re.fullmatch(r"(?:ERROR|WARNING) line \d+:\d+ .+", line) for line in lines):
        return CountRecovery(len(lines), "RECOVERED_FROM_COMPLETE_PROBLEM_DIAGNOSTICS")
    return CountRecovery(None, "PARSER_TECHNICAL_FAILURE_OR_MISSING_COUNT")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def key(row: dict[str, Any]) -> tuple[str, str, str]:
    return row["language"].lower(), row["task"], row.get("operator", row.get("mutant", ""))


def snapshot_evidence(source: Path, iteration: int) -> tuple[Path, dict[str, Any], Path]:
    root = next(parent for parent in source.parents if (parent / "manifest.json").is_file())
    matches = []
    suffix = f"/transformation/iteration-{iteration:03d}/{source.name}"
    for path in sorted((root / "stages/syntax-validation/attempts").glob("*/evidence.json")):
        observation = json.loads(path.read_text(encoding="utf-8"))
        if any(item.endswith(suffix) for item in observation["details"]["transformations"]):
            matches.append((path, observation))
    if not matches:
        raise ValueError(f"no matching parser observation: {source}")
    path, observation = matches[-1]
    return path, observation, root


def ppl_records(snapshots: list[dict[str, str]], inventory: dict[str, str]) -> list[dict[str, Any]]:
    records = []
    loc_helper = LOC_DEFINITION
    inventory[str(loc_helper)] = sha256(loc_helper)
    spec = importlib.util.spec_from_file_location("frozen_candidate_loc_definition", loc_helper)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    expected_driver = "b8881756652ad18579332a6706c7748704fa63d83036f48b49d85aa039afec66"
    expected_driver_main = "99e8c7cd76d5899d963423d5c81a0738875336a08d76a9a8ba89fef511bb44f5"
    for row in snapshots:
        if row["source_available"] != "True":
            continue
        source = repository_path(row["source_path"])
        if sha256(source) != row["source_sha256"]:
            raise ValueError(f"candidate hash mismatch: {source}")
        inventory[str(source)] = row["source_sha256"]
        evidence_path, evidence, root = snapshot_evidence(source, int(row["iteration"]))
        inventory[str(evidence_path)] = sha256(evidence_path)
        parsed = row["parsed"] == "True"
        count = int(row["problem_count"]) if row["problem_count"] else None
        recovery = CountRecovery(count, "RECORDED_OBSERVATION" if count is not None else "UNAVAILABLE")
        csv_path = ""
        if row["language"] == "etl":
            for filename, expected in (("run_parser.py", expected_driver), ("validate_etl_syntax.py", expected_driver_main)):
                driver = root / "workspaces/etl-parser" / filename
                if sha256(driver) != expected:
                    raise ValueError(f"unrecognized archived ETL driver: {driver}")
                inventory[str(driver)] = expected
            diagnostic = "\n".join(evidence["details"].get("diagnostics", {}).values())
            saved_csv = root / "observations/syntax-validation/generated_transformation_syntax.csv"
            if saved_csv.is_file():
                inventory[str(saved_csv)] = sha256(saved_csv)
                matches = [item for item in read_csv(saved_csv) if item["path"].endswith(f"/iteration-{int(row['iteration']):03d}/{source.name}")]
                if len(matches) > 1:
                    raise ValueError(f"duplicate ETL parser CSV identity: {saved_csv}")
                if matches:
                    count = int(matches[0]["problem_count"])
                    if (matches[0]["parsed"] == "True") != parsed:
                        raise ValueError(f"ETL parser verdict mismatch: {saved_csv}")
                    csv_path = str(saved_csv)
            recovery = recover_etl_count(parsed, diagnostic, count)
        loc = int(row["candidate_loc"])
        if loc <= 0 or loc != helper.code_loc(source.read_text(encoding="utf-8"), row["language"]):
            raise ValueError(f"invalid or changed candidate LoC: {source}")
        records.append({field: row[field] for field in ("run_id", "source_group", "batch_group", "batch_id", "language", "task", "snapshot", "iteration", "source_path", "source_sha256")} | {
            "parsed": parsed, "candidate_loc": loc, "problem_count": recovery.count,
            "ppl": None if recovery.count is None else recovery.count / loc, "count_basis": recovery.basis,
            "issue_scope": "ALL_REPORTED_XTEXT_ISSUES_INCLUDING_LINKAGE_AND_WARNINGS" if row["language"] == "reactions" else "REPORTED_PARSER_PROBLEMS",
            "parser_evidence": str(evidence_path), "parser_csv": csv_path})
    return records


def grouped_ppl(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in records:
        for scope, name in (("language", row["language"]), ("batch", row["batch_group"]),
                            ("batch_language", row["batch_group"] + "/" + row["language"]), ("overall", "all")):
            groups[(scope, name, row["snapshot"])].append(row)
    result = []
    for (scope, name, snapshot), rows in sorted(groups.items()):
        measured = [row for row in rows if row["ppl"] is not None]
        total = sum(row["ppl"] for row in measured)
        complete = len(measured) == len(rows)
        result.append({"scope": scope, "name": name, "snapshot": snapshot, "candidates": len(rows),
            "measured": len(measured), "missing": len(rows) - len(measured),
            "sum_problems": sum(row["problem_count"] for row in measured),
            "sum_individual_ppl": total, "mean_ppl": total / len(measured) if complete and measured else None,
            "partial_observed_mean": total / len(measured) if measured else None,
            "coverage_complete": complete, "pooling_caution": "Counts have different parser issue scopes across languages; not a pure syntax-error ranking."})
    return result


def verify_probe_reports(probe_directories: Iterable[Path], inventory: dict[str, str]) -> dict[tuple[str, str, str], list[str]]:
    witnesses = defaultdict(list)
    for directory in probe_directories:
        manifest_path = directory / "freeze.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if sha256(directory / "executor.py") != manifest["executor_sha256"]:
            raise ValueError(f"archived probe executor differs: {directory}")
        integrity = json.loads((directory / "integrity.json").read_text(encoding="utf-8"))
        if sha256(manifest_path) != integrity["freeze_sha256"]:
            raise ValueError(f"probe freeze changed: {directory}")
        inventory[str(manifest_path)] = integrity["freeze_sha256"]
        for name, digest in integrity["raw_hashes"].items():
            path = directory / "raw" / name
            if sha256(path) != digest:
                raise ValueError(f"probe raw evidence changed: {path}")
            inventory[str(path)] = digest
        for recorded, digest in manifest["protected"].items():
            path = repository_path(recorded)
            if sha256(path) != digest:
                raise ValueError(f"probe protected input changed: {path}")
            inventory[str(path)] = digest
        results_path = directory / "results.json"
        inventory[str(results_path)] = sha256(results_path)
        results = json.loads(results_path.read_text(encoding="utf-8"))
        references = {(row["job"]["language"], row["job"]["task"]): row for row in results if row["job"]["role"] == "reference"}
        for row in results:
            job = row["job"]
            if job["role"] == "reference":
                continue
            reference = references[(job["language"], job["task"])]
            if is_counterexample(reference, row):
                witnesses[(job["language"], job["task"], job["role"])].append(str(directory / "raw" / job["job_id"] / "execution.json"))
    return witnesses


def verify_original_observations(observations: list[dict[str, str]], tables: Path,
                                 campaign: Path, inventory: dict[str, str]) -> None:
    """Check selected identities and every outcome against the original selected CSV."""
    runs_path = tables / "Runs.csv"
    trace_path = campaign / "run-mutant-matches.csv"
    inventory[str(runs_path)], inventory[str(trace_path)] = sha256(runs_path), sha256(trace_path)
    runs = read_csv(runs_path)
    traces = {(row["run_id"], row["operator"]): row for row in read_csv(trace_path)}
    selected = {row["run_id"] for row in runs}
    if len(runs) != 564 or len(selected) != 564 or {row["run_id"] for row in observations} != selected:
        raise ValueError("mutation observations do not match the 564 selected run identities")
    sources = {}
    for row in observations:
        trace = traces[(row["run_id"], row["operator"])]
        source = repository_path(trace["artifact"])
        if source not in sources:
            sources[source] = read_csv(source)
            inventory[str(source)] = sha256(source)
        original = sources[source][int(trace["csv_line"]) - 2]
        if original["run_id"] != row["run_id"] or original[row["operator"]] != row["outcome"] or original["reference_result"] != row["reference_result"]:
            raise ValueError(f"mutation outcome differs from original CSV: {row['run_id']}/{row['operator']}")


def verify_final_model_proofs(inventory: dict[str, str]) -> None:
    """Check the fixed metamodel opposites and exact eager source-rule assignments."""
    for task, source_name, target_name, opposite in (
            ("Grafcet2PetriNet_All", "Grafcet", "PetriNet", "net"),
            ("PetriNet2Grafcet_All", "PetriNet", "Grafcet", "grafcet")):
        reference = TARGET.benchmark / "tasks/atl/references" / (task + ".atl")
        mutant = MUTANTS_DIR / "ATL" / task / "M8.atl"
        text = reference.read_text(encoding="utf-8")
        original = "elements <- g.elements," if source_name == "Grafcet" else "elements <- p.elements,"
        modified = "elements <- g.elements->excluding(g.elements->first())," if source_name == "Grafcet" else "elements <- p.elements->excluding(p.elements->first()),"
        if text.count(original) != 1 or text.replace(original, modified, 1) != mutant.read_text(encoding="utf-8"):
            raise ValueError(f"equivalence proof is not the exact single-source replacement: {task}")
        assignments = "net <- g.grafcet," if source_name == "Grafcet" else "grafcet <- p.net,"
        if text.count(assignments) != 4:
            raise ValueError(f"unexpected opposite assignment coverage: {task}")
        metamodel = TARGET.engine_harness("atl") / "src/main/resources/metamodels" / (target_name + ".ecore")
        benchmark_model = TARGET.benchmark / "metamodels/additional_models/ATL_model" / (target_name + ".ecore")
        if sha256(metamodel) != sha256(benchmark_model):
            raise ValueError(f"benchmark and harness metamodels differ: {target_name}")
        features = [node for node in ET.parse(metamodel).getroot().iter("eStructuralFeatures") if node.get("name") == "elements"]
        if len(features) != 1 or features[0].get("ordered") != "false" or not features[0].get("eOpposite", "").endswith("Element/" + opposite):
            raise ValueError(f"fixed metamodel does not establish the opposite/set proof: {target_name}")
        inventory[str(reference)], inventory[str(mutant)] = sha256(reference), sha256(mutant)
        inventory[str(metamodel)], inventory[str(benchmark_model)] = sha256(metamodel), sha256(benchmark_model)


def mutant_records(unique: list[dict[str, str]], observations: list[dict[str, str]],
                   manual_methods: list[dict[str, Any]], entries: list[dict[str, Any]],
                   new_witnesses: dict[tuple[str, str, str], list[str]], inventory: dict[str, str]) -> list[dict[str, Any]]:
    """Join exact source identities, keeping retrospective witnesses separate."""
    by_identity = defaultdict(list)
    by_job = defaultdict(list)
    for row in observations:
        by_identity[key(row)].append(row)
    for row in manual_methods:
        by_job[row["job_id"]].append(row)
    catalog = {key(entry): entry for entry in entries if entry["status"] == "PRESENT"}
    records = []
    for row in unique:
        identity = key(row)
        entry = catalog[identity]
        path = REPO_ROOT / entry["file"]
        if sha256(path) != entry["mutant_sha256"] or row["sha256"] != entry["mutant_sha256"]:
            raise ValueError(f"mutant identity differs: {identity}")
        reference = REPO_ROOT / entry["reference"]
        inventory[str(path)], inventory[str(reference)] = sha256(path), sha256(reference)
        kills = [item for item in by_identity[identity] if item["reference_result"] == "PASS" and item["outcome"] == "KILLED"]
        if len(kills) != int(row["generated_killed"]):
            raise ValueError(f"unique and repeated generated detection totals differ: {identity}")
        manual = row["manual_outcome"] == "KILLED"
        if manual:
            reference_job = f"references--{identity[0]}--{identity[1]}--primary--reference"
            if behavioral_outcome(by_job[reference_job]) != "PASS" or behavioral_outcome(by_job[row["job_id"]]) != "ASSERTION_FAILURE":
                raise ValueError(f"manual witness is not reference-passing behavior: {identity}")
            for job_id in (reference_job, row["job_id"]):
                raw = CAMPAIGN_RAW_DIR / job_id / "attempt-001/trial/execution.json"
                raw_fact = json.loads(raw.read_text(encoding="utf-8"))
                if raw_fact["source_sha256"] != (sha256(reference) if job_id == reference_job else entry["mutant_sha256"]):
                    raise ValueError(f"manual raw source identity differs: {raw}")
                expected = "PASS" if job_id == reference_job else "ASSERTION_FAILURE"
                if behavioral_outcome(raw_fact["methods"]) != expected:
                    raise ValueError(f"manual raw verdict differs: {raw}")
                inventory[str(raw)] = sha256(raw)
        new = new_witnesses.get(identity, [])
        status = "NON_EQUIVALENT_RECORDED_COUNTEREXAMPLE" if kills or manual or new else "UNRESOLVED"
        proof = ""
        if identity in (("atl", "Grafcet2PetriNet_All", "M8"), ("atl", "PetriNet2Grafcet_All", "M8")):
            if kills or manual or new:
                raise ValueError(f"assertion witness contradicts proposed equivalence proof: {identity}")
            status = "EQUIVALENT_FINAL_MODEL_PROOF"
            proof = "Eager element rules assign each mapped element's opposite container (net/grafcet), restoring the omitted containment member. Both elements collections are unordered, and all concrete source element types are covered. Same final attributed target graph for well-formed models of the fixed metamodel; excludes traces, malformed inputs and extensions. See equivalence-proofs.md."
        risk = ""
        if status == "UNRESOLVED":
            if row["manual_outcome"] == "UNAVAILABLE":
                risk = "Original legacy reference/context unqualified; unavailable manual evidence is not equivalence."
            elif int(row["generated_valid"]) == 0 or row["manual_outcome"] == "RUNTIME_ERROR":
                risk = "Technical-only observations; executable semantic counterexample remains unavailable."
            else:
                risk = "Existing suites survived; changed source alone does not establish equivalence or a validated counterexample."
        records.append({"language": identity[0], "task": identity[1], "operator": identity[2],
            "category": entry["category"], "status": status, "reference": str(reference), "reference_sha256": sha256(reference),
            "mutant": str(path), "mutant_sha256": entry["mutant_sha256"], "original": entry["original"], "mutated": entry["mutated"],
            "manual_outcome": row["manual_outcome"], "manual_witness": str(CAMPAIGN_RAW_DIR / row["job_id"] / "attempt-001/trial/execution.json") if manual else "",
            "generated_kill_observations": len(kills), "generated_witness_run_ids": "|".join(item["run_id"] for item in kills),
            "generated_evidence_limit": "Stored selected CSV outcome plus deterministic executable-assertion classification; full original mutation process logs were not retained.",
            "new_probe_witnesses": "|".join(new), "proof": proof, "remaining_risk": risk})
    if len(records) != 289 or len({key(row) for row in records}) != 289:
        raise ValueError("equivalence population is not 289 unique mutants")
    return records


def mutation_summary(records: list[dict[str, Any]], observations: list[dict[str, str]]) -> list[dict[str, Any]]:
    dispositions = {key(row): row["status"] for row in records}
    groups = defaultdict(list)
    for row in observations:
        for scope, name in (("language", row["language"]), ("batch", row["batch_group"]),
                            ("batch_language", row["batch_group"] + "/" + row["language"]), ("overall", "all")):
            groups[(scope, name)].append(row)
    result = []
    for (scope, name), rows in sorted(groups.items()):
        judged = [row for row in rows if row["reference_result"] == "PASS"]
        executable = [row for row in judged if row["outcome"] in ("KILLED", "SURVIVED")]
        killed = sum(row["outcome"] == "KILLED" for row in executable)
        known = sum(dispositions[key(row)] == "NON_EQUIVALENT_RECORDED_COUNTEREXAMPLE" for row in executable)
        unknown = sum(dispositions[key(row)] == "UNRESOLVED" for row in executable)
        equivalent = len(executable) - known - unknown
        interval = mutation_interval(killed, known, unknown)
        result.append({"scope": scope, "name": name, "unit": "REPEATED_RUN_MUTANT_OBSERVATION",
            "selected_observations": len(rows), "reference_passing": len(judged), "not_judged": len(rows) - len(judged),
            "technical": len(judged) - len(executable), "executable": len(executable), "equivalent_excluded": equivalent,
            **asdict(interval), "denominator_scope": "Reference-passing executable observations only; errors excluded and reported. Equivalence proofs restricted to final target models of fixed metamodels."})
    for language in ("atl", "etl", "qvto", "reactions", "all"):
        selected = [row for row in records if language == "all" or row["language"] == language]
        counts = Counter(row["status"] for row in selected)
        killed = sum(row["generated_kill_observations"] > 0 for row in selected)
        interval = mutation_interval(killed, counts["NON_EQUIVALENT_RECORDED_COUNTEREXAMPLE"], counts["UNRESOLVED"])
        result.append({"scope": "unique_catalogue", "name": language, "unit": "UNIQUE_TASK_MUTANT_ANY_SELECTED_GENERATED_SUITE",
            "catalogue": len(selected), "equivalent_excluded": counts["EQUIVALENT_FINAL_MODEL_PROOF"],
            **asdict(interval), "denominator_scope": "Unique catalogue identities; ANY generated kill across twelve suites. Missing and technical original opportunities do not imply survival; catalogue coverage rate, not per-suite accuracy."})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probes", type=Path, action="append", default=[])
    args = parser.parse_args()
    inventory = {}
    tables = RQ_SUMMARY_DIR
    campaign = CAMPAIGN_REPORT_DIR
    paths = {"snapshots": tables / "Snapshots.csv", "observations": tables / "Mutants.csv",
        "unique": campaign / "unique-mutant-matches.csv", "manual_methods": campaign / "derived-method-outcomes.json",
        "catalogue": MUTANT_CATALOG}
    inventory.update({str(path): sha256(path) for path in paths.values()})
    snapshots, observations, unique = (read_csv(paths[name]) for name in ("snapshots", "observations", "unique"))
    if len(observations) != 3468 or len({(row["run_id"], row["operator"]) for row in observations}) != 3468:
        raise ValueError("unexpected or duplicate selected mutation population")
    verify_original_observations(observations, tables, campaign, inventory)
    verify_final_model_proofs(inventory)
    ppl = ppl_records(snapshots, inventory)
    witnesses = verify_probe_reports(args.probes, inventory)
    manual_methods = json.loads(paths["manual_methods"].read_text(encoding="utf-8"))
    entries = json.loads(paths["catalogue"].read_text(encoding="utf-8"))["mutants"]
    mutants = mutant_records(unique, observations, manual_methods, entries, witnesses, inventory)
    scores = mutation_summary(mutants, observations)
    # CSV summaries are an intermediate export; JSON is the canonical new report.
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), output / "reducer.py")
    write_json(output / "protocol.json", {"schema_version": "retrospective-equivalence-analysis-1",
        "original_campaign_unchanged": True, "classification": "Recorded behavioral counterexample proves non-equivalence. Surviving/technical outcomes remain unresolved unless a separately stated source proof establishes final-model equivalence.",
        "new_probe_kills": "Only equivalence evidence; original generated/manual kill counts never increased.",
        "not_ms_q": "Retrospective evidence collection is not the original independent predeclared qualification population. No result is labelled MS_Q.",
        "equivalence_domain": "Final attributed target models, fixed metamodels, well-formed inputs; unordered references treated as sets. ATL proofs exclude temporal traces and metamodel extensions.",
        "bounds": "Fixed original assertion-kill numerator. Minimum denominator=known non-equivalent units; maximum adds unresolved units. Exact only with zero unresolved units in stated executable population. No timeouts/errors counted as kills.",
        "ppl": "Arithmetic mean of individual problem_count / nonempty noncomment candidate LoC, using the previous hash-verified LoC table. Technical missing counts are unavailable, never zero. Reactions raw issue density includes accepted linkage issues/warnings; not pure grammar-error density.",
        "etl_inference": "All 97 saved runs retain identical checked parser drivers. CSV is overwritten between iterations: match exact candidate path, then recover full normal ParseProblem lines or infer zero from the saved driver's pass contract. A parser exception gives no numeric count.",
        "historical_limitations": "Historical dirty execution states and complete initial LLM requests remain unavailable. No strict historical oracle independence or clean-commit reproduction claim.",
        "probe_directories": portable([str(path.resolve()) for path in args.probes])})
    for name, rows in (("ppl-snapshots", ppl), ("ppl-by-language-and-batch", grouped_ppl(ppl)),
                       ("mutant-equivalence", mutants), ("mutation-scores-and-bounds", scores)):
        rows = portable(rows)
        write_json(output / (name + ".json"), rows)
        fields = list(dict.fromkeys(field for row in rows for field in row))
        write_csv(output / (name + ".csv"), [{field: row.get(field) for field in fields} for row in rows])
    for path, digest in inventory.items():
        if sha256(repository_path(path)) != digest:
            raise ValueError(f"input changed during reduction: {path}")
    write_json(output / "source-inventory.json", portable(inventory))
    write_json(output / "validation.json", {"selected_run_mutant_observations": len(observations),
        "unique_mutants": len(mutants), "dispositions": dict(Counter(row["status"] for row in mutants)),
        "new_unique_counterexamples": len(witnesses), "ppl_snapshot_records": len(ppl),
        "verified_input_files": len(inventory), "all_inputs_unchanged": True})
    print(json.dumps(json.loads((output / "validation.json").read_text(encoding="utf-8")), indent=2))


if __name__ == "__main__":
    main()
