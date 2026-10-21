"""Separate RQ1–RQ4 reporting over selected immutable experiment artifacts.

Writes the tables of ``rq-summary-20261012-v1`` (``Runs``, ``Snapshots``,
``Mutants``, ``Metrics``, ...) into a new directory. ``Snapshots.csv`` and
``Mutants.csv`` are the inputs of ``evaluation.equivalence_analysis``. Candidate
LoC uses ``evaluation.reduce_tables.code_loc``. Every run copies this script
into its output as provenance. The input locations are the constants at the
top of this file; every path written into the output is repository-relative.

    PYTHONPATH=pipeline/src:. .venv/bin/python -m evaluation.reduce_metrics \
      --output artifacts/legacy-suite-evaluation/<new-directory>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation import reduce_tables as helper
from evaluation import rq_metrics as rq
from evaluation._common import SelectedRun, portable, repository_path
from evaluation.legacy_pilot.assessment import endpoints
from llm4mtl.paths import REPO_ROOT, TARGET, repository_relative


# Inputs, relative to the repository. Change them here to reduce another selection.
SELECTION_ROOT = TARGET.artifacts / "Chosen_for_evaluation"
MUTANT_CATALOG = REPO_ROOT / "evaluation" / "mutants" / "manifest.json"
INVENTORIED_CODE = (
    REPO_ROOT / "evaluation" / "rq_metrics.py",
    REPO_ROOT / "evaluation" / "_common.py",
    REPO_ROOT / "evaluation" / "legacy_pilot" / "assessment.py",
)


GROUPS = {
    "GPT-5.6-Luna_only/batch_004": ("004", "OpenAI only"),
    "GPT-5.6-Luna_only/batch_005": ("005", "OpenAI only"),
    "GPT-5.6-Luna_only/batch_006": ("006", "OpenAI only"),
    "GPT-5.6-Luna_only/batch_007": ("007", "OpenAI only"),
    "Mixed_1_batch_008": ("008", "Mixed 1"),
    "Mixed_2_batch_009-011": ("009–011", "Mixed 2"),
    "Mixed_3_batch_012": ("012", "Mixed 3"),
    "Gemini_batch_013": ("013", "Gemini"),
    "Claude_batch_014": ("014", "Claude"),
    "GPT-5.1/1_batch_016-017": ("016–017", "GPT-5.1"),
    "GPT-5.1/2_batch_018-019": ("018–019", "GPT-5.1"),
    "GPT-5.1/3_batch_020": ("020", "GPT-5.1"),
}
LANGUAGES = ("atl", "etl", "qvto", "reactions")
EXCLUDED_ATTEMPTS = frozenset({
    "qvto-mappingextensionmerges-20261003-114748-886068",
    "qvto-mappingextensionmerges-20261003-125626-419565",
    "etl-equivalent-20260930-143552-371918",
    "etl-multiple_targets-20260930-160643-167720",
})
DEFINITIONS = [
    ("RQ1", "cr_initial", "Executability", "Initial suite", "generated suite", "Executable initial suites / generated initial suites. No-verdict suites remain in denominator."),
    ("RQ1", "tc_initial", "Test Correctness", "Initial suite", "generated suite", "Initial suites passing the reference / executable initial suites."),
    ("RQ1", "cr_final", "Executability", "Final suite", "generated suite", "Executable final suites / generated final suites. No-verdict suites remain in denominator."),
    ("RQ1", "tc_final", "Test Correctness", "Final suite", "generated suite", "Final suites passing the reference / executable final suites."),
    ("RQ1", "cr_all", "Executability", "All suite generations", "generated suite iteration", "Executable suites / all generated suite iterations; repeated generations are not independent runs."),
    ("RQ1", "tc_all", "Test Correctness", "All suite generations", "generated suite iteration", "Reference-passing suites / all executable suite iterations."),
    ("RQ2", "ur_T0", "Unparsed Rate", "T0", "transformation", "Parser-rejected initial saved transformations / initial transformations with recorded parser verdict."),
    ("RQ2", "ur_T1", "Unparsed Rate", "T1", "transformation", "Rejected post-syntax/pre-first-semantic-refinement candidates / recorded parser verdicts at that exact endpoint."),
    ("RQ2", "ur_T2", "Unparsed Rate", "T2", "transformation", "Rejected final adopted candidates / recorded parser verdicts at that exact endpoint."),
    ("RQ2", "ppl_T0", "Mean PPL", "T0", "parser problems / candidate LoC", "Arithmetic mean of individual problem_count / non-empty non-comment candidate LoC; require complete comparable counts."),
    ("RQ2", "ppl_T1", "Mean PPL", "T1", "parser problems / candidate LoC", "Same candidate-LoC definition at T1. No all-language result if any language lacks comparable counts."),
    ("RQ2", "ppl_T2", "Mean PPL", "T2", "parser problems / candidate LoC", "Same candidate-LoC definition at final adopted T2."),
    ("RQ3", "pass1", "Pass@1", "Initial candidate", "run / own validated generated suite", "Initially parsable iteration-000 candidates passing their FIRST recorded semantic execution / all initially parsable candidates. Coverage must be complete; no later execution substitutes for the first."),
    ("RQ3", "suite_first", "Complete-suite pass", "First semantic execution", "run / own validated generated suite", "First execution passing all cases / runs reaching semantic execution. Includes candidates repaired by syntax feedback; this is not Pass@1."),
    ("RQ3", "suite_final", "Complete-suite pass", "Final adopted candidate", "run / own validated generated suite", "Final adopted candidates passing all cases / runs reaching semantic execution. A final adopted endpoint without a matching execution is non-PASS, retained separately."),
    ("RQ4", "ms_strict", "Classical MS: killed / non-equivalent", "Final generated suite", "run–mutant observation", "Undefined: catalogue and matrix do not establish the non-equivalent denominator. Never infer that a survivor is equivalent or that every applicable mutant is proven non-equivalent."),
    ("RQ4", "catalogue_kill", "Observed catalogue kill rate", "Final generated suite", "run–mutant observation", "KILLED / all applicable observations in runs with reference_result=PASS; includes ERROR/PARSE_FAILED in denominator, excludes NOT_JUDGED. Reproduces matrix kill_rate definition, not equivalence-adjusted MS."),
    ("RQ4", "emkr", "Executable mutant kill rate (EMKR)", "Final generated suite", "run–mutant observation", "KILLED / (KILLED + SURVIVED), only reference-passing generated suites. ERROR/PARSE_FAILED are not kills and stay separate."),
    ("RQ4", "mutant_exec", "Mutant executability", "Final generated suite", "run–mutant observation", "(KILLED + SURVIVED) / applicable observations of reference-passing generated suites."),
    ("RQ4", "union_kill", "Unique executable mutant union detection", "Final generated suites pooled", "unique task–mutant", "Distinct mutants killed at least once / distinct mutants with at least one KILLED or SURVIVED observation in this scope. Multiple suites provide multiple chances; not independent trials or MS_Q."),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    rows = portable(rows)
    headers = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def suite_counts(states: list[str]) -> tuple[int, int, int]:
    executable = sum(s in rq.EXECUTABLE_SUITE_STATES for s in states)
    return len(states), executable, states.count(rq.SUITE_VALID)


def build(output: Path) -> None:
    if output.exists():
        raise ValueError("Output directory must be new; original derived reports are not overwritten")
    assert suite_counts(["VALID", "REFERENCE_INVALID", "NOT_EXECUTABLE", "NO_VERDICT"]) == (4, 2, 1)
    assert 2 / (2 + 1) != 2 / (2 + 1 + 1)
    selection = SELECTION_ROOT
    groups = rq.discover_groups(selection)
    assert {g.name for g in groups} == set(GROUPS)
    assert all(len(g.runs) == 47 for g in groups)
    helper_path = Path(helper.__file__)
    assert helper.code_loc("-- header\nrule R {\n'http://x' -- inline\n}\n", "atl") == 3
    catalog_path = MUTANT_CATALOG
    catalog = read_json(catalog_path)
    present = {(r["language"].lower(), r["task"], r["mutant"]): r for r in catalog["mutants"] if r["status"] == "PRESENT"}
    assert len(present) == 289
    assert not any(any(k in r for k in ("equivalent", "non_equivalent", "qualified")) for r in catalog["mutants"])
    source_paths = {helper_path, catalog_path, *INVENTORIED_CODE}
    source_paths.update(selection.rglob("*.csv"))
    source_paths.update(selection.rglob("excluded-runs.txt"))
    for group in groups:
        for batch, run_id in group.runs:
            root = TARGET.run_dir(batch, run_id)
            source_paths.update([root / "manifest.json", root / "result.json", root / "events.jsonl"])
            for directory in ("stages", "generations", "refinements", "observations", "transformation"):
                source_paths.update((root / directory).rglob("*.json"))
                source_paths.update((root / directory).rglob("*.xml"))
            for metadata in (root / "transformation").glob("iteration-*/metadata.json"):
                for record in read_json(metadata)["transformations"]:
                    path = REPO_ROOT / record["path"]
                    source_paths.add(path if path.is_file() else root / record["path"])
            source_paths.update(TARGET.run_diagnoses_dir(batch, run_id).glob("attempt-*/diagnosis.json"))
    inventory = {repository_relative(p): digest(p) for p in sorted(source_paths) if p.is_file()}
    facts = []
    records = []
    snapshots = []
    mutations = []
    for group in sorted(groups, key=lambda g: list(GROUPS).index(g.name)):
        group_label, configuration = GROUPS[group.name]
        for batch, run_id in group.runs:
            fact = rq.read_run_facts(group, batch, run_id)
            root = TARGET.run_dir(batch, run_id)
            manifest, terminal = read_json(root / "manifest.json"), read_json(root / "result.json")
            run = SelectedRun(run_id, root, manifest, terminal)
            ends = endpoints(run)
            if ends:
                assert ends.post[0] == terminal["transformation_iteration"], run_id
            indices = {} if ends is None else {"T0": ends.initial, "T1": ends.pre or ends.post, "T2": ends.post}
            parsed = {v.iteration: v for v in fact.syntax}
            first = fact.executions[0] if fact.executions else None
            initial_parsed = parsed.get(0)
            first_candidate_observed = bool(first and first.transformation_iteration == 0)
            if initial_parsed and initial_parsed.is_parsed:
                assert first_candidate_observed, f"Missing first-candidate semantic execution: {run_id}"
            if first:
                suite = next(s for s in fact.suites if s.iteration == first.suite_iteration)
                assert suite.state == rq.SUITE_VALID, f"First generated suite was not reference-qualified: {run_id}"
            initial_generation = root / "generations/transformation/iteration-000/generation.json"
            generation = read_json(initial_generation) if initial_generation.is_file() else {}
            row = {"run_id": run_id, "source_group": group.name, "batch_group": group_label, "configuration": configuration,
                "batch_id": batch, "language": fact.language, "task": manifest["task"],
                "initial_suite_state": fact.suites[0].state if fact.suites else "NO_VERDICT",
                "final_suite_state": fact.suites[-1].state if fact.suites else "NO_VERDICT",
                "suite_generations": len(fact.suites), "executable_suite_generations": suite_counts([s.state for s in fact.suites])[1],
                "reference_passing_suite_generations": suite_counts([s.state for s in fact.suites])[2],
                "source_available": ends is not None, "initial_parsed": bool(initial_parsed and initial_parsed.is_parsed),
                "initial_parser_observed": initial_parsed is not None,
                "first_candidate_semantic_observed": first_candidate_observed,
                "first_candidate_full_pass": bool(first_candidate_observed and first.is_passed),
                "semantic_executed": first is not None, "first_semantic_full_pass": bool(first and first.is_passed),
                "final_semantic_full_pass": bool(first and rq._final_passes(fact)),
                "final_adopted_iteration": fact.final_transformation_iteration,
                "final_adopted_semantic_observed": bool(first and fact.executions[-1].transformation_iteration == fact.final_transformation_iteration),
                "initial_generation_model": generation.get("model"), "git_dirty": manifest["provenance"]["git_dirty"],
                "manifest_path": str(root / "manifest.json"), "result_path": str(root / "result.json")}
            records.append(row)
            facts.append(fact)
            for state in ("T0", "T1", "T2"):
                index, path = indices.get(state, (None, None))
                verdict = parsed.get(index)
                snapshots.append({"run_id": run_id, "source_group": group.name, "batch_group": group_label,
                    "batch_id": batch, "language": fact.language, "task": manifest["task"], "snapshot": state,
                    "iteration": index, "source_available": path is not None, "source_path": str(path) if path else None,
                    "source_sha256": digest(path) if path else None, "parser_observed": verdict is not None,
                    "parsed": verdict.is_parsed if verdict else None, "problem_count": verdict.problem_count if verdict else None,
                    "candidate_loc": helper.code_loc(path.read_text(encoding="utf-8"), fact.language) if path else None})
            matrix = fact.mutant_row
            assert matrix and matrix["run_id"] == run_id
            applicable = {operator: value for operator, value in matrix.items() if rq.OPERATOR_COLUMN.fullmatch(operator) and value != "N/A"}
            assert len(applicable) == int(matrix["mutants"])
            assert sum(s == "KILLED" for s in applicable.values()) == int(matrix["killed"])
            for operator, outcome in applicable.items():
                entry = present[(fact.language, manifest["task"], operator)]
                mutations.append({"run_id": run_id, "source_group": group.name, "batch_group": group_label, "batch_id": batch,
                    "language": fact.language, "task": manifest["task"], "operator": operator,
                    "reference_result": matrix["reference_result"], "outcome": outcome,
                    "source_path": entry["file"], "mutant_sha256": entry["mutant_sha256"], "equivalence_status": "NOT_ASSESSED"})
    assert len(records) == len({r["run_id"] for r in records}) == 564
    assert not EXCLUDED_ATTEMPTS.intersection(r["run_id"] for r in records)
    assert len({(r["language"], r["task"]) for r in records}) == 47
    assert sum(r["source_available"] for r in records) == 487
    comparable = rq.comparable_problem_languages(facts)
    assert comparable == {"atl", "qvto"}
    for snapshot in snapshots:
        n, loc = snapshot["problem_count"], snapshot["candidate_loc"]
        snapshot["ppl_comparable"] = snapshot["language"] in comparable
        snapshot["ppl"] = n / loc if n is not None and loc and snapshot["ppl_comparable"] else None
    assert len(mutations) == len({(r["run_id"], r["operator"]) for r in mutations}) == 3468
    assert len({(r["language"], r["task"], r["operator"]) for r in mutations}) == 289
    observed_outcomes = Counter(r["outcome"] for r in mutations)
    assert observed_outcomes == {"KILLED": 2274, "SURVIVED": 570, "ERROR": 100, "NOT_JUDGED": 524}
    cohorts = [{"scope_type": "all", "scope": "ALL", "language": "ALL", "configuration": "All selected configurations", "batch_group": "ALL", "members": records}]
    for lang in LANGUAGES:
        cohorts.append({"scope_type": "language", "scope": lang, "language": lang, "configuration": "All selected configurations", "batch_group": "ALL", "members": [r for r in records if r["language"] == lang]})
    for group_name, (label, configuration) in GROUPS.items():
        members = [r for r in records if r["source_group"] == group_name]
        cohorts.append({"scope_type": "batch_group", "scope": label, "language": "ALL", "configuration": configuration, "batch_group": label, "members": members})
        for lang in LANGUAGES:
            cohorts.append({"scope_type": "batch_group_language", "scope": label, "language": lang, "configuration": configuration, "batch_group": label, "members": [r for r in members if r["language"] == lang]})
    for batch in sorted({r["batch_id"] for r in records}):
        members = [r for r in records if r["batch_id"] == batch]
        for lang in ("ALL", *LANGUAGES):
            subset = [r for r in members if lang == "ALL" or r["language"] == lang]
            if subset:
                cohorts.append({"scope_type": "physical_batch" if lang == "ALL" else "physical_batch_language", "scope": batch,
                    "language": lang, "configuration": subset[0]["configuration"], "batch_group": subset[0]["batch_group"], "members": subset})
    metrics = []
    overview = []
    by_definition = {code: (rqid, label, state, unit, definition) for rqid, code, label, state, unit, definition in DEFINITIONS}
    for number, cohort in enumerate(cohorts):
        members = cohort["members"]
        ids = {r["run_id"] for r in members}
        saved = sum(r["source_available"] for r in members)
        base = {k: v for k, v in cohort.items() if k != "members"}
        base.update(cohort_id=f"C{number:03d}", selected_runs=len(members), saved_transformations=saved)
        values = {}

        def add(code: str, numerator: int | float | None, denominator: int | None, *, status: str = "AVAILABLE",
                eligible: int | None = None, observed: int | None = None, note: str = "") -> None:
            rqid, label, stage, unit, definition = by_definition[code]
            if status == "AVAILABLE" and not denominator:
                status = "NO_ELIGIBLE_OBSERVATIONS"
            value = numerator / denominator if status == "AVAILABLE" and numerator is not None and denominator else None
            record = {**base, "rq": rqid, "metric_code": code, "metric": label, "stage": stage,
                "oracle": "own validated generated suite" if rqid == "RQ3" else "reference transformation" if rqid == "RQ1" else "stored parser" if rqid == "RQ2" else "final generated suite",
                "numerator": numerator, "denominator": denominator, "value": value, "status": status, "unit": unit,
                "eligible": eligible, "observed": observed, "note": note or definition}
            metrics.append(record)
            values[code] = value

        for state, field in (("initial", "initial_suite_state"), ("final", "final_suite_state")):
            n, executable, valid = suite_counts([r[field] for r in members])
            add(f"cr_{state}", executable, n)
            add(f"tc_{state}", valid, executable)
        add("cr_all", sum(r["executable_suite_generations"] for r in members), sum(r["suite_generations"] for r in members))
        add("tc_all", sum(r["reference_passing_suite_generations"] for r in members), sum(r["executable_suite_generations"] for r in members))
        for state in ("T0", "T1", "T2"):
            chosen = [s for s in snapshots if s["run_id"] in ids and s["snapshot"] == state]
            verdicts = [s for s in chosen if s["parser_observed"]]
            assert len(verdicts) == saved
            add(f"ur_{state}", sum(not s["parsed"] for s in verdicts), len(verdicts), eligible=saved, observed=len(verdicts))
            densities = [s["ppl"] for s in chosen if s["ppl"] is not None]
            complete = len(densities) == saved and saved > 0
            add(f"ppl_{state}", sum(densities) if densities else None, len(densities),
                status="AVAILABLE" if complete else "INCOMPLETE_OR_NONCOMPARABLE_COUNTS", eligible=saved, observed=len(densities),
                note="Mean of per-candidate ratios" if complete else "ETL counts missing; Reactions counts not comparable. No mean is exposed for a partial population; missing source slots remain separate.")
        parsable = [r for r in members if r["initial_parser_observed"] and r["initial_parsed"]]
        add("pass1", sum(r["first_candidate_full_pass"] for r in parsable), len(parsable), eligible=len(parsable), observed=sum(r["first_candidate_semantic_observed"] for r in parsable))
        executed = [r for r in members if r["semantic_executed"]]
        add("suite_first", sum(r["first_semantic_full_pass"] for r in executed), len(executed))
        add("suite_final", sum(r["final_semantic_full_pass"] for r in executed), len(executed), eligible=len(executed), observed=sum(r["final_adopted_semantic_observed"] for r in executed))
        selected_mutations = [m for m in mutations if m["run_id"] in ids]
        judged = [m for m in selected_mutations if m["reference_result"] == "PASS"]
        assert all(m["outcome"] != "NOT_JUDGED" for m in judged)
        states = Counter(m["outcome"] for m in judged)
        killed, survived = states["KILLED"], states["SURVIVED"]
        add("ms_strict", killed, None, status="NON_EQUIVALENT_DENOMINATOR_NOT_ESTABLISHED")
        add("catalogue_kill", killed, len(judged))
        add("emkr", killed, killed + survived)
        add("mutant_exec", killed + survived, len(judged))
        unique = defaultdict(list)
        for m in judged:
            if m["outcome"] in ("KILLED", "SURVIVED"):
                unique[(m["language"], m["task"], m["operator"])].append(m["outcome"])
        add("union_kill", sum("KILLED" in outcomes for outcomes in unique.values()), len(unique))
        overview.append({**base, **values, "mutants_killed": killed, "mutants_survived": survived,
            "mutants_error": states["ERROR"], "mutants_parse_failed": states["PARSE_FAILED"],
            "mutants_not_judged": sum(m["outcome"] == "NOT_JUDGED" for m in selected_mutations),
            "unique_catalogue_mutants": len({(m["language"], m["task"], m["operator"]) for m in selected_mutations}),
            "final_endpoint_without_execution": sum(not r["final_adopted_semantic_observed"] for r in executed)})
    global_rows = {r["metric_code"]: r for r in metrics if r["scope_type"] == "all"}
    controls = {"cr_initial": (495, 564), "tc_initial": (336, 495), "cr_final": (546, 564), "tc_final": (484, 546),
        "cr_all": (910, 1046), "tc_all": (500, 910), "ur_T0": (64, 487), "ur_T1": (14, 487), "ur_T2": (15, 487),
        "pass1": (293, 423), "suite_first": (309, 473), "suite_final": (402, 473), "catalogue_kill": (2274, 2944), "emkr": (2274, 2844)}
    for code, (n, d) in controls.items():
        assert (global_rows[code]["numerator"], global_rows[code]["denominator"]) == (n, d), code
    canonical = list(csv.DictReader((selection / "rq-metrics.csv").open(encoding="utf-8")))
    mapping = {"cr_initial": "executability_rate_initial", "cr_final": "executability_rate_final", "tc_initial": "reference_pass_rate_initial", "tc_final": "reference_pass_rate_final", "cr_all": "executability_rate_all_attempts", "tc_all": "reference_pass_rate_all_attempts", "suite_first": "full_suite_success_before", "suite_final": "full_suite_success_after", "emkr": "emkr", "catalogue_kill": "applicable_mutant_kill_rate", "mutant_exec": "mutant_executability_rate"}
    equal_checks = 0
    group_reverse = {v[0]: k for k, v in GROUPS.items()}
    for metric in metrics:
        scope_type = metric["scope_type"]
        if metric["metric_code"] not in mapping or scope_type not in ("all", "language", "batch_group", "batch_group_language"):
            continue
        expected_scope = "all" if scope_type in ("all", "language") else "group"
        expected_name = "ALL" if expected_scope == "all" else group_reverse[metric["scope"]]
        old = next(r for r in canonical if r["scope_type"] == expected_scope and r["scope"] == expected_name and r["language"] == metric["language"] and r["metric"] == mapping[metric["metric_code"]])
        assert (metric["numerator"], metric["denominator"]) == (int(old["numerator"]), int(old["denominator"])), metric
        equal_checks += 1
    assert all(digest(repository_path(path)) == expected for path, expected in inventory.items()), "Authoritative input changed during reduction"
    output.mkdir(parents=True)
    definitions = [{"rq": rqid, "metric_code": code, "metric": label, "stage": state, "unit": unit, "definition": definition} for rqid, code, label, state, unit, definition in DEFINITIONS]
    tables = {"Metrics": metrics, "Overview": overview, "Runs": records, "Snapshots": snapshots, "Mutants": mutations, "Definitions": definitions}
    (output / "tables.json").write_text(json.dumps(portable(tables), ensure_ascii=False, indent=2), encoding="utf-8")
    for name, rows in tables.items():
        write_csv(output / f"{name}.csv", rows)
    for name, kinds in (("by-language", {"all", "language"}), ("by-batch-group", {"batch_group"}), ("by-batch-language", {"batch_group_language"}), ("by-physical-batch", {"physical_batch", "physical_batch_language"})):
        write_csv(output / f"{name}.csv", [r for r in metrics if r["scope_type"] in kinds])
    write_csv(output / "source-inventory.csv", [{"path": path, "sha256": h} for path, h in inventory.items()])
    freeze = {"schema_version": "rq-metric-view-1.0", "selected_run_ids": [r["run_id"] for r in records], "excluded_orchestration_attempts": sorted(EXCLUDED_ATTEMPTS),
        "group_mapping": GROUPS, "selection_root": str(selection), "definitions": definitions, "source_files": len(inventory),
        "metric_oracle": "run-specific reference-validated generated suites, not fixed manual/held-out suites", "equivalence_assessed": False, "new_pipeline_or_llm_calls": 0}
    (output / "population-and-protocol.json").write_text(json.dumps(portable(freeze), ensure_ascii=False, indent=2), encoding="utf-8")
    validation = {"selected_runs": 564, "groups": 12, "tasks": 47, "saved_transformations": 487, "physical_batches": len({r["batch_id"] for r in records}),
        "cohorts": len(cohorts), "metric_rows": len(metrics), "canonical_count_checks_equal": equal_checks,
        "source_files_verified": len(inventory), "mutation_observations": 3468, "unique_mutants": 289,
        "mutation_outcomes": dict(observed_outcomes), "first_parsable_candidate_coverage": (293, 423),
        "missing_initial_transformations": 77, "comparable_ppl_languages": sorted(comparable),
        "global_counts": {key: (r["numerator"], r["denominator"]) for key, r in global_rows.items()}, "protected_input_changes": []}
    (output / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    shutil.copy2(Path(__file__), output / "reduce_metrics.py")
    print(json.dumps(validation, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output.resolve())
