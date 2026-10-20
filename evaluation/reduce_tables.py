"""Read-only reduction of the supplementary legacy-suite evaluation tables."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation import rq_metrics as rq
from evaluation._common import portable, repository_path
from evaluation.legacy_pilot.assessment import selected_runs
from llm4mtl.paths import REPO_ROOT, TARGET, repository_relative


# Inputs, relative to the repository. Change them here to reduce another
# selection or another frozen legacy campaign.
SELECTION_ROOT = TARGET.artifacts / "Chosen_for_evaluation"
LEGACY_EVALUATION_ROOT = TARGET.artifacts / "legacy-suite-evaluation"
CAMPAIGN_DIR = LEGACY_EVALUATION_ROOT / "campaign-20261008-v1"
CAMPAIGN_REPORT_DIR = CAMPAIGN_DIR / "report-v3"
SNAPSHOT_CAMPAIGN_DIR = LEGACY_EVALUATION_ROOT / "snapshots-20261009-v1"
INVENTORIED_CODE = (REPO_ROOT / "evaluation" / "rq_metrics.py", REPO_ROOT / "evaluation" / "legacy_pilot" / "assessment.py")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_loc(source: str, language: str) -> int:
    """Count candidate-source lines containing non-comment code, preserving strings."""
    line_comments = ("--", "//") if language in ("atl", "qvto") else ("//",)
    block = False
    quote = ""
    count = 0
    for line in source.splitlines():
        code = False
        index = 0
        while index < len(line):
            char = line[index]
            if block:
                if line.startswith("*/", index):
                    block = False
                    index += 2
                else:
                    index += 1
                continue
            if quote:
                code = True
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    if index + 1 < len(line) and line[index + 1] == quote:
                        index += 2
                        continue
                    quote = ""
                index += 1
                continue
            if line.startswith("/*", index):
                block = True
                index += 2
                continue
            if any(line.startswith(marker, index) for marker in line_comments):
                break
            if char in ("'", '"'):
                quote = char
            if not char.isspace():
                code = True
            index += 1
        count += code
    return count


def choose_t1(generations: dict[int, dict[str, Any]]) -> int:
    """The saved endpoint before any semantic transformation refinement."""
    semantic = sorted(i for i, g in generations.items() if g.get("purpose") == "semantic_refinement")
    if semantic:
        first = semantic[0]
        previous = generations[first]["input_artifact_iteration"]
        if previous != first - 1:
            raise ValueError("semantic refinement input is not the previous version")
        return previous
    return max(generations)


def primary_pairs(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r["context"] == "primary"]


def fraction(numerator: int | float, denominator: int, complete: bool = True) -> float | None:
    return numerator / denominator if denominator and complete else None


def typed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    numeric = re.compile(r"^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$")
    keep_text = {"seed", "source", "sha256", "evidence_sha256", "run_id", "task", "scope", "group", "batch_id", "operator", "category"}
    result = []
    for row in rows:
        values = {}
        for key, value in row.items():
            if value == "":
                values[key] = None
            elif isinstance(value, str) and value in ("True", "False", "true", "false"):
                values[key] = value.lower() == "true"
            elif isinstance(value, str) and key not in keep_text and numeric.fullmatch(value):
                values[key] = float(value) if any(c in value for c in ".eE") else int(value)
            else:
                values[key] = value
        result.append(values)
    return result


def scopes(runs: list[dict[str, Any]]) -> list[tuple[str, str, str, list[dict[str, Any]]]]:
    result = []
    for kind, names in (("all", ["ALL"]), ("group", sorted({r["group"] for r in runs})),
                        ("family", sorted({r["family"] for r in runs}))):
        for name in names:
            members = [r for r in runs if kind == "all" or r[kind] == name]
            for language in ["ALL"] + sorted({r["language"] for r in members}):
                subset = [r for r in members if language == "ALL" or r["language"] == language]
                result.append((kind, name, language, subset))
    for language, task in sorted({(r["language"], r["task"]) for r in runs}):
        result.append(("task", task, language, [r for r in runs if (r["language"], r["task"]) == (language, task)]))
    return result


def build(output: Path) -> None:
    if output.exists():
        raise ValueError("output directory must be new")
    assert code_loc("-- comment\nrule R {\n 'http://x--y' -- trailing\n}\n", "atl") == 3
    assert code_loc('/* a\n b */\nvar x = "/* literal */";\n// comment\n', "etl") == 1
    assert code_loc("/*comment*/ rule R {} // comment\n", "reactions") == 1
    assert fraction(1, 0) is None and fraction(0, 4) == 0 and fraction(2, 3, False) is None
    selection = SELECTION_ROOT
    campaign = CAMPAIGN_DIR
    report = CAMPAIGN_REPORT_DIR
    full_campaign = SNAPSHOT_CAMPAIGN_DIR
    full_outcomes = json.loads((full_campaign / "snapshot-outcomes.json").read_text(encoding="utf-8"))
    full_index = {(r["run_id"], r["snapshot"]): r for r in full_outcomes}
    assert len(full_index) == 1692
    full_methods = typed(read_csv(full_campaign / "derived-method-outcomes.csv"))
    full_methods_index = defaultdict(list)
    for method in full_methods:
        full_methods_index[method["job_id"]].append(method)
    source_paths = set(selection.rglob("*.csv")) | set(selection.rglob("*.txt"))
    source_paths.update(report.glob("*.csv"))
    source_paths.update([campaign / "freeze.json", campaign / "paired-population.json", campaign / "task-to-test-mapping.csv"])
    groups = rq.discover_groups(selection)
    facts = {run_id: rq.read_run_facts(g, batch, run_id) for g in groups for batch, run_id in g.runs}
    archive_runs = {r.run_id: r for r in selected_runs()}
    comparable = rq.comparable_problem_languages(facts.values())
    failure_rows = {r["run_id"]: r for r in typed(read_csv(selection / "failure-analysis/failure-runs.csv"))}
    pairs_all = typed(read_csv(report / "pairs.csv"))
    pairs = {r["run_id"]: r for r in primary_pairs(pairs_all)}
    qualification = json.loads((full_campaign / "reference-qualification.json").read_text(encoding="utf-8"))
    qualification = [{k: v for k, v in r.items() if k not in ("runtime_properties", "runtime_dependencies")} for r in qualification]
    qualified = {(r["language"], r["task"]): r for r in qualification if r["context"] == "primary"}
    test_mapping = typed(read_csv(campaign / "task-to-test-mapping.csv"))
    for control in qualification:
        cases = [r for r in test_mapping if (r["language"], r["task"]) == (control["language"], control["task"])]
        control["behavioral_methods_expected"] = sum(r["strength"] == "behavioral" for r in cases)
        control["weak_methods"] = sum(r["strength"] == "source_only_weak" for r in cases)
        control["smoke_methods"] = sum(r["strength"] in ("resource_smoke", "execution_smoke") for r in cases)
        control["qualification_reason_detail"] = "No behavioral legacy method mapped; source-only/smoke checks do not qualify an oracle" if not control["behavioral_methods_expected"] else control["reason"]
    runs = []
    snapshots = []
    for group in groups:
        original = {r["run_id"]: r for r in typed(read_csv(selection / group.name / "batch-runs.csv"))}
        family = "Mixed" if group.name.startswith("Mixed_") else group.model
        for batch, run_id in group.runs:
            archive = archive_runs[run_id]
            fact = facts[run_id]
            run = {**failure_rows[run_id], **original[run_id], "group": group.name, "family": family,
                   "manifest_transformation_model": archive.manifest.get("transformation_model"),
                   "manifest_test_generation_model": archive.manifest.get("test_generation_model"),
                   "git_commit": archive.manifest["provenance"]["git_commit"],
                   "git_dirty": archive.manifest["provenance"]["git_dirty"],
                   "legacy_paired_selected": run_id in pairs,
                   "legacy_reference_qualified": qualified[(fact.language, archive.task)]["qualified"],
                   "legacy_qualification_reason": qualified[(fact.language, archive.task)]["reason"]}
            source_paths.update([archive.root / "manifest.json", archive.root / "result.json", archive.root / "events.jsonl"])
            for folder in ("stages", "generations", "refinements", "diagnosis"):
                source_paths.update((archive.root / folder).rglob("*.json"))
            source_paths.update((archive.root / "observations").rglob("*.xml"))
            source_paths.update((archive.root / "observations").rglob("suite_execution.json"))
            versions = {}
            for metadata in sorted((archive.root / "transformation").glob("iteration-*/metadata.json")):
                data = json.loads(metadata.read_text(encoding="utf-8"))
                path = REPO_ROOT / data["transformations"][0]["path"]
                if not path.is_file():
                    path = archive.root / data["transformations"][0]["path"]
                if not path.is_file():
                    raise ValueError(f"missing transformation: {metadata}")
                versions[data["iteration"]] = path
                source_paths.update([metadata, path])
            generations = {int(p.parent.name.split("-")[1]): json.loads(p.read_text(encoding="utf-8"))
                           for p in (archive.root / "generations/transformation").glob("*/generation.json")}
            run["initial_generation_model"] = generations.get(0, {}).get("model")
            run["initial_generation_provider"] = generations.get(0, {}).get("provider")
            run["recorded_transformation_models"] = json.dumps(sorted({g["model"] for g in generations.values() if g.get("model")}), ensure_ascii=False)
            test_records = [json.loads(p.read_text(encoding="utf-8")) for p in (archive.root / "generations/semantic-test").glob("*/generation.json")]
            run["recorded_test_generation_models"] = json.dumps(sorted({g["model"] for g in test_records if g.get("model")}), ensure_ascii=False)
            if versions and sorted(versions) != list(range(max(versions) + 1)):
                raise ValueError(f"non-contiguous transformations: {run_id}")
            run["saved_transformation_versions"] = len(versions)
            run["transformation_available"] = bool(versions)
            run["missing_transformation_reason"] = None if versions else archive.terminal_result["outcome_code"]
            runs.append(run)
            syntax = {v.iteration: v for v in fact.syntax}
            endpoints = {"T0": 0, "T1": choose_t1(generations), "T2": max(versions)} if versions else {}
            if versions:
                if max(versions) != archive.terminal_result["transformation_iteration"]:
                    raise ValueError(f"final endpoint mismatch: {run_id}")
                if run_id in pairs and endpoints["T1"] != pairs[run_id]["Tpre_iteration"]:
                    raise ValueError(f"T1/Tpre mismatch: {run_id}")
            for name in ("T0", "T1", "T2"):
                iteration = endpoints.get(name)
                path = versions.get(iteration)
                verdict = syntax.get(iteration)
                same_version = sorted((e for e in fact.executions if e.transformation_iteration == iteration), key=lambda e: e.attempt)
                generated = same_version[-1] if same_version else None
                source_hash = digest(path) if path else None
                loc = code_loc(path.read_text(encoding="utf-8"), fact.language) if path else None
                count = verdict.problem_count if verdict else None
                execution = full_index[(run_id, name)]
                if execution["source_sha256"] != source_hash or execution["iteration"] != iteration:
                    raise ValueError(f"new campaign snapshot mismatch: {run_id}/{name}")
                is_qualified = execution["reference_qualified"]
                legacy_outcome = execution["legacy_outcome"]
                reason = execution["qualification_reason"] if legacy_outcome == "UNAVAILABLE" else None
                snapshot = {"group": group.name, "family": family, "batch_id": batch, "run_id": run_id,
                    "language": fact.language, "task": archive.task, "snapshot": name, "iteration": iteration,
                    "source_available": bool(path), "source": str(path) if path else None, "sha256": source_hash,
                    "generation_purpose": generations[iteration].get("purpose") if path else None,
                    "generation_model": generations[iteration].get("model") if path else None,
                    "generation_provider": generations[iteration].get("provider") if path else None,
                    "parser_observed": verdict is not None, "parsed": verdict.is_parsed if verdict else None,
                    "problem_count": count, "non_comment_non_empty_loc": loc,
                    "ppl_comparable": fact.language in comparable,
                    "ppl": count / loc if count is not None and loc and fact.language in comparable else None,
                    "ppl_unavailable_reason": None if fact.language in comparable and verdict and count is not None and loc else
                        ("ETL parser problem counts missing" if fact.language == "etl" else
                         "Reactions reports nonzero problems on accepted sources" if fact.language == "reactions" else
                         "no parser verdict or candidate source"),
                    "generated_observed": generated is not None,
                    "generated_full_pass": generated.is_passed if generated else None,
                    "generated_suite_iteration": generated.suite_iteration if generated else None,
                    "generated_execution_attempt": generated.attempt if generated else None,
                    "legacy_reference_qualified": is_qualified, "legacy_outcome": legacy_outcome,
                    "legacy_unavailable_reason": reason,
                    "legacy_evidence_job": execution["job_id"],
                    "legacy_evidence_kind": "fresh frozen task/source-hash execution" if path and is_qualified else "unavailable",
                    "legacy_behavioral_methods": execution["behavioral_methods"],
                    "legacy_behavioral_methods_pass": execution["behavioral_methods_pass"],
                    "fixed_inputs_identical": execution["fixed_inputs_identical"],
                    "runtime_dependencies_identical": execution["runtime_dependencies_identical"],
                    "runtime_properties_identical": execution["runtime_properties_identical"],
                    "later_syntax_sensitivity": pairs.get(run_id, {}).get("syntax_sensitivity_exclusion", False)}
                snapshots.append(snapshot)
    assert len(runs) == len({r["run_id"] for r in runs}) == 564
    assert len(groups) == 12 and all(len(g.runs) == 47 for g in groups)
    assert sum(r["transformation_available"] for r in runs) == 487
    assert len(pairs) == 120
    assert len({(r["language"], r["task"]) for r in runs}) == 47
    all_scopes = scopes(runs)
    snapshot_index = {(r["run_id"], r["snapshot"]): r for r in snapshots}
    transition_rows = []
    for kind, scope, language, members in all_scopes:
        for before, after in (("T0", "T1"), ("T1", "T2"), ("T0", "T2")):
            eligible = [r for r in members if snapshot_index[(r["run_id"], before)]["source_available"]
                        and snapshot_index[(r["run_id"], before)]["legacy_reference_qualified"]]
            for sensitivity, population in (("all_qualified_saved", eligible),
                ("exclude_later_syntax", [r for r in eligible if not snapshot_index[(r["run_id"], before)]["later_syntax_sensitivity"]])):
                endpoints = [(snapshot_index[(r["run_id"], before)], snapshot_index[(r["run_id"], after)]) for r in population]
                transitions = Counter((a["legacy_outcome"] == "PASS", b["legacy_outcome"] == "PASS") for a, b in endpoints)
                transition_rows.append({"scope_type": kind, "scope": scope, "language": language,
                    "before": before, "after": after, "sensitivity": sensitivity, "paired_runs": len(population),
                    "fail_to_pass": transitions[(False, True)], "pass_to_fail": transitions[(True, False)],
                    "pass_to_pass": transitions[(True, True)], "fail_to_fail": transitions[(False, False)],
                    "assertion_failure_to_pass": sum(a["legacy_outcome"] == "ASSERTION_FAILURE" and b["legacy_outcome"] == "PASS" for a, b in endpoints),
                    "technical_failure_to_pass": sum(a["legacy_outcome"] in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR") and b["legacy_outcome"] == "PASS" for a, b in endpoints),
                    "note": "Non-PASS includes technical failures; identical sources share one frozen execution, so unchanged endpoints are deterministic repeats."})
    syntax_rows = []
    legacy_rows = []
    generated_rows = []
    pair_summary = []
    for kind, scope, language, members in all_scopes:
        ids = {r["run_id"] for r in members}
        key = {"scope_type": kind, "scope": scope, "language": language}
        for state in ("T0", "T1", "T2"):
            selected = [s for s in snapshots if s["run_id"] in ids and s["snapshot"] == state]
            source_n = sum(s["source_available"] for s in selected)
            observed = [s for s in selected if s["parser_observed"]]
            ppl = [s["ppl"] for s in selected if s["ppl"] is not None]
            complete_ppl = len(ppl) == source_n and source_n > 0
            syntax_rows.append({**key, "snapshot": state, "selected_runs": len(members),
                "source_available": source_n, "parser_observed": len(observed),
                "unparsed_num": sum(not s["parsed"] for s in observed), "unparsed_den": len(observed),
                "unparsed_rate": fraction(sum(not s["parsed"] for s in observed), len(observed)),
                "ppl_sum": sum(ppl), "ppl_den": len(ppl), "ppl_complete": complete_ppl,
                "mean_ppl": sum(ppl) / len(ppl) if complete_ppl else None,
                "mean_ppl_observed": sum(ppl) / len(ppl) if ppl else None,
                "ppl_note": "Complete comparable counts" if complete_ppl else "Incomplete or non-comparable language counts; no all-language PPLs"})
            eligible = [s for s in selected if s["source_available"] and s["legacy_reference_qualified"]]
            tested = [s for s in eligible if s["legacy_outcome"] != "UNAVAILABLE"]
            outcomes = Counter(s["legacy_outcome"] for s in tested)
            complete = len(tested) == len(eligible)
            parsable = [s for s in eligible if s["parsed"] is True]
            parsable_tested = [s for s in parsable if s["legacy_outcome"] != "UNAVAILABLE"]
            pass1_complete = len(parsable_tested) == len(parsable)
            legacy_rows.append({**key, "snapshot": state, "selected_runs": len(members),
                "source_available": source_n, "unqualified_sources": source_n - len(eligible),
                "full_pass_num": outcomes["PASS"], "full_pass_den": len(eligible),
                "legacy_observed": len(tested), "full_pass_complete": complete,
                "full_pass_rate": fraction(outcomes["PASS"], len(eligible), complete),
                "observed_pass_num": outcomes["PASS"], "observed_pass_den": len(tested),
                "observed_pass_rate": fraction(outcomes["PASS"], len(tested)),
                "assertion_failure": outcomes["ASSERTION_FAILURE"], "compilation_error": outcomes["COMPILATION_ERROR"],
                "runtime_error": outcomes["RUNTIME_ERROR"], "infrastructure_error": outcomes["INFRASTRUCTURE_ERROR"],
                "unavailable": len(eligible) - len(tested),
                "pass1_num": sum(s["legacy_outcome"] == "PASS" for s in parsable_tested) if state == "T0" else None,
                "pass1_den": len(parsable) if state == "T0" else None,
                "pass1_observed": len(parsable_tested) if state == "T0" else None,
                "pass1_complete": pass1_complete if state == "T0" else False,
                "pass1_rate": fraction(sum(s["legacy_outcome"] == "PASS" for s in parsable_tested), len(parsable), pass1_complete) if state == "T0" else None,
                "behavioral_method_pass_num": sum(s["legacy_behavioral_methods_pass"] or 0 for s in eligible),
                "behavioral_method_pass_den": sum(s["legacy_behavioral_methods"] or 0 for s in eligible),
                "behavioral_method_pass_rate": fraction(sum(s["legacy_behavioral_methods_pass"] or 0 for s in eligible), sum(s["legacy_behavioral_methods"] or 0 for s in eligible)),
                "note": "Fresh frozen T0/T1/T2 campaign. Behavioral qualified task contexts. No missing/technical outcomes silently excluded; conditional Pass@1 only at T0."})
        scoped_facts = [facts[r["run_id"]] for r in members]
        for metric, chosen, passing in (
            ("first_semantic_execution_success", [f for f in scoped_facts if f.executions], lambda f: f.executions[0].is_passed),
            ("final_generated_suite_success", [f for f in scoped_facts if f.executions], rq._final_passes),
            ("observed_exact_T0_generated_suite_success", [f for f in scoped_facts if any(e.transformation_iteration == 0 for e in f.executions)],
             lambda f: next(e for e in f.executions if e.transformation_iteration == 0).is_passed)):
            generated_rows.append({**key, "metric": metric, "selected_runs": len(members),
                "numerator": sum(passing(f) for f in chosen), "denominator": len(chosen),
                "value": fraction(sum(passing(f) for f in chosen), len(chosen)),
                "note": "Run's own validated generated suite. First semantic execution may follow syntax refinement. No fixed independent T0 oracle."})
        for context, subset in (("primary", [p for p in pairs_all if p["run_id"] in ids and p["context"] == "primary"]),
                                ("primary_without_later_syntax", [p for p in pairs_all if p["run_id"] in ids and p["context"] == "primary" and not p["syntax_sensitivity_exclusion"]]),
                                ("reactions_full", [p for p in pairs_all if p["run_id"] in ids and p["context"] == "full"])):
            if not subset:
                continue
            counts = Counter((p["Tpre_outcome"] == "PASS", p["Tpost_outcome"] == "PASS") for p in subset)
            pair_summary.append({**key, "context": context, "pairs": len(subset),
                "pre_pass_num": sum(p["Tpre_outcome"] == "PASS" for p in subset), "pre_pass_den": len(subset),
                "pre_pass_rate": fraction(sum(p["Tpre_outcome"] == "PASS" for p in subset), len(subset)),
                "post_pass_num": sum(p["Tpost_outcome"] == "PASS" for p in subset), "post_pass_den": len(subset),
                "post_pass_rate": fraction(sum(p["Tpost_outcome"] == "PASS" for p in subset), len(subset)),
                "fail_to_pass": counts[(False, True)], "pass_to_fail": counts[(True, False)],
                "pass_to_pass": counts[(True, True)], "fail_to_fail": counts[(False, False)],
                "technical_pre": sum(p["Tpre_outcome"] in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR") for p in subset),
                "technical_post": sum(p["Tpost_outcome"] in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR") for p in subset),
                "assertion_pre": sum(p["Tpre_outcome"] == "ASSERTION_FAILURE" for p in subset),
                "assertion_post": sum(p["Tpost_outcome"] == "ASSERTION_FAILURE" for p in subset),
                "note": "Non-PASS transitions include technical failures. Tpre is not automatically T0. Context views overlap."})
    enriched_pairs = [{"group": next(r["group"] for r in runs if r["run_id"] == p["run_id"]),
                       "batch_id": next(r["batch_id"] for r in runs if r["run_id"] == p["run_id"]), **p} for p in pairs_all]
    pair_reproduction = []
    for pair in primary_pairs(pairs_all):
        pre = snapshot_index[(pair["run_id"], "T1")]
        post = snapshot_index[(pair["run_id"], "T2")]
        pair_reproduction.append({"run_id": pair["run_id"], "language": pair["language"], "task": pair["task"],
            "old_Tpre_outcome": pair["Tpre_outcome"], "new_T1_outcome": pre["legacy_outcome"],
            "old_Tpost_outcome": pair["Tpost_outcome"], "new_T2_outcome": post["legacy_outcome"],
            "pre_source_hash_identical": digest(repository_path(pair["Tpre_source"])) == pre["sha256"],
            "post_source_hash_identical": digest(repository_path(pair["Tpost_source"])) == post["sha256"],
            "pre_outcome_identical": pair["Tpre_outcome"] == pre["legacy_outcome"],
            "post_outcome_identical": pair["Tpost_outcome"] == post["legacy_outcome"]})
    mutant_rows = typed(read_csv(report / "run-mutant-matches.csv"))
    unique_rows = typed(read_csv(report / "unique-mutant-matches.csv"))
    manual_rows = typed(read_csv(report / "manual-mutants.csv"))
    assert len(manual_rows) == len({(r["language"], r["task"], r["operator"]) for r in manual_rows}) == 289
    assert len(mutant_rows) == len({(r["run_id"], r["operator"]) for r in mutant_rows}) == 3468
    assert all(r["run_id"] in facts for r in mutant_rows)
    mutation_summary = []
    mutation_scopes = list(all_scopes)
    for operator in sorted({r["operator"] for r in mutant_rows}):
        for language in ("ALL", "atl", "etl", "qvto", "reactions"):
            mutation_scopes.append(("operator", operator, language, [r for r in runs if language == "ALL" or r["language"] == language]))
    for kind, scope, language, members in mutation_scopes:
        ids = {r["run_id"] for r in members}
        observations = [r for r in mutant_rows if r["run_id"] in ids]
        if kind == "operator":
            observations = [r for r in observations if r["operator"] == scope]
        identities = {(r["language"], r["task"], r["operator"]) for r in observations}
        matched = [r for r in unique_rows if (r["language"], r["task"], r["operator"]) in identities]
        # Global unique rows are only valid for scopes spanning all twelve configurations.
        by_identity = defaultdict(list)
        for row in observations:
            by_identity[(row["language"], row["task"], row["operator"])].append(row)
        unique_counts = Counter()
        for identity, obs in by_identity.items():
            valid = [r for r in obs if r["reference_result"] == "PASS" and r["generated_outcome"] in ("KILLED", "SURVIVED")]
            manual = obs[0]["manual_outcome"]
            if manual not in ("KILLED", "SURVIVED"):
                label = "UNINTERPRETABLE"
            elif not valid:
                label = "UNMATCHED"
            else:
                g = any(r["generated_outcome"] == "KILLED" for r in valid)
                label = "BOTH" if g and manual == "KILLED" else "GENERATED_ONLY" if g else "MANUAL_ONLY" if manual == "KILLED" else "NEITHER"
            unique_counts[label] += 1
        repeated_counts = Counter(r["match_class"] for r in observations)
        states = Counter(r["generated_outcome"] for r in observations)
        manual_states = Counter(r["manual_outcome"] for r in matched)
        comparable_n = sum(unique_counts[k] for k in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER"))
        mutation_summary.append({"scope_type": kind, "scope": scope, "language": language,
            "selected_runs": len(members), "unique_mutants": len(identities), "run_mutant_observations": len(observations),
            "generated_killed": states["KILLED"], "generated_survived": states["SURVIVED"],
            "generated_error": states["ERROR"], "generated_not_judged": states["NOT_JUDGED"],
            "emkr_num": states["KILLED"], "emkr_den": states["KILLED"] + states["SURVIVED"],
            "emkr_rate": fraction(states["KILLED"], states["KILLED"] + states["SURVIVED"]),
            "manual_killed_unique": manual_states["KILLED"], "manual_survived_unique": manual_states["SURVIVED"],
            "manual_runtime_unique": manual_states["RUNTIME_ERROR"], "manual_unavailable_unique": manual_states["UNAVAILABLE"],
            "comparable_unique": comparable_n, "both_unique": unique_counts["BOTH"],
            "generated_only_unique": unique_counts["GENERATED_ONLY"], "manual_only_unique": unique_counts["MANUAL_ONLY"],
            "neither_unique": unique_counts["NEITHER"], "unmatched_unique": unique_counts["UNMATCHED"],
            "uninterpretable_unique": unique_counts["UNINTERPRETABLE"],
            "both_repeated": repeated_counts["BOTH"], "generated_only_repeated": repeated_counts["GENERATED_ONLY"],
            "manual_only_repeated": repeated_counts["MANUAL_ONLY"], "neither_repeated": repeated_counts["NEITHER"],
            "note": "Unique generated detections are a union within this scope; manual result reused. Unequal opportunities. Not MS_Q."})
    recomputed = rq.compute_rows(groups)
    frozen_rq = typed(read_csv(selection / "rq-metrics.csv"))
    assert len(recomputed) == len(frozen_rq)
    for a, b in zip(recomputed, frozen_rq):
        for k in rq.OUTPUT_FIELDS:
            av, bv = a[k], b[k]
            if av in ("", None) and bv in ("", None):
                continue
            if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
                assert abs(av-bv) < 0.0000011, (k, av, bv)
            else:
                assert av == bv, (k, av, bv)
    historical = []
    original_paper = {
        "atl": {"Unparsed Rate": 0.13, "Mean candidate PPLs": 0.0019, "Legacy Pass@1 among qualified parsable T0": 0.67},
        "etl": {"Unparsed Rate": 0.20, "Mean candidate PPLs": 0.0209, "Legacy Pass@1 among qualified parsable T0": 0.50},
        "qvto": {"Unparsed Rate": 0.00, "Mean candidate PPLs": 0.0000, "Legacy Pass@1 among qualified parsable T0": 0.50},
        "reactions": {"Unparsed Rate": 0.25, "Mean candidate PPLs": 0.0342, "Legacy Pass@1 among qualified parsable T0": 0.50},
    }
    for lang in ("ALL", "atl", "etl", "qvto", "reactions"):
        for metric, snapshot, table, field in (("Unparsed Rate", "T0", syntax_rows, "unparsed_rate"),
            ("Post-syntax Unparsed Rate", "T1", syntax_rows, "unparsed_rate"),
            ("Mean candidate PPLs", "T0", syntax_rows, "mean_ppl"),
            ("Post-syntax mean candidate PPLs", "T1", syntax_rows, "mean_ppl"),
            ("Legacy Pass@1 among qualified parsable T0", "T0", legacy_rows, "pass1_rate"),
            ("Final behavioral legacy full-suite pass", "T2", legacy_rows, "full_pass_rate")):
            item = next(r for r in table if r["scope_type"] == "family" and r["scope"] == "GPT-5.1" and r["language"] == lang and r["snapshot"] == snapshot)
            historical.append({"language": lang, "metric": metric, "snapshot": snapshot,
                "current_gpt51_value": item[field], "original_llm4mtls_value": original_paper.get(lang, {}).get(metric),
                "current_numerator": item.get("pass1_num") if metric.startswith("Legacy Pass@1") else item.get("unparsed_num") if "Unparsed" in metric else None,
                "current_denominator": item.get("pass1_den") if metric.startswith("Legacy Pass@1") else item.get("unparsed_den") if "Unparsed" in metric else item.get("ppl_den") if "PPLs" in metric else item.get("full_pass_den"),
                "original_numerator": None, "original_denominator": None,
                "original_strategy": "FS + GR", "original_model": "GPT-5.1 (published model label)",
                "source": "https://arxiv.org/html/2606.25193v1", "original_table": 3 if metric == "Unparsed Rate" else 4 if metric == "Mean candidate PPLs" else 5 if metric.startswith("Legacy Pass@1") else None,
                "current_status": "AVAILABLE" if item[field] is not None else "UNAVAILABLE",
                "original_status": "VERIFIED_PUBLISHED_ROUNDED_AGGREGATE; raw numerator/denominator not verified" if metric in original_paper.get(lang, {}) else "NOT_REPORTED: no aggregate or refinement endpoint in original paper",
                "comparability": "Descriptive historical comparison only. Published PPL definition uses candidate LoC, while local legacy analysis uses reference LoC; published raw calculation not reconstructed. Current behavioral-qualified suites, Reactions contexts, parsers and three repeated groups are not a controlled reproduction of published all-associated-test Pass@1."})
    overview = []
    for metric, num, den, note in (("Selected runs", 564, None, "12 groups x 47 tasks"),
        ("Saved transformations", 487, 564, "77 selected runs have no saved transformation"),
        ("Initially unparsed", 64, 487, "Archived parser verdict"), ("Post-syntax unparsed", 14, 487, "Archived parser verdict"),
        ("Final unparsed", 15, 487, "Archived parser verdict"),
        ("Legacy paired Tpre full pass", 8, 120, "Primary task contexts; selected semantic-refinement runs"),
        ("Legacy paired Tpost full pass", 100, 120, "Same qualified tests and fixtures as Tpre"),
        ("Manual semantic mutant kills", 147, 289, "Catalogue description; not MS_Q; includes technical/unavailable identities in denominator"),
        ("Manual mutant survivors", 118, 289, "Separate from eight runtime errors and sixteen unavailable"),
        ("Manual mutant runtime errors", 8, 289, "Not semantic kills"), ("Manual mutant unavailable", 16, 289, "Unqualified reference/context"),
        ("Matched unique BOTH", 145, 261, "Generated union has up to twelve opportunities per identity"),
        ("Matched unique GENERATED_ONLY", 87, 261, "Comparable task-mutant identities"),
        ("Matched unique MANUAL_ONLY", 0, 261, "Comparable task-mutant identities"),
        ("Matched unique NEITHER", 29, 261, "Comparable task-mutant identities")):
        overview.append({"metric": metric, "numerator": num, "denominator": den, "value": fraction(num, den) if den else None, "note": note})
    readme = [{"topic": key, "definition": text} for key, text in (
        ("Population", "Exactly the twelve selected groups and 564 run IDs. Batch 015 excluded as a test batch. Failed attempts outside the selected IDs never enter aggregates."),
        ("T0", "Saved transformation iteration-000, before syntax or semantic transformation feedback."),
        ("T1", "Input to the first semantic transformation refinement, after preceding syntax repairs. If no semantic transformation refinement occurred, final saved version. T1 may equal T0 or T2."),
        ("T2", "Final saved transformation iteration, verified against terminal result.json. Includes later syntax refinement."),
        ("Unparsed Rate", "Number of failed archived parser verdicts / number of available parser verdicts at that exact snapshot. Missing transformations are separate, not parse failures."),
        ("PPLs", "Per-candidate parser problems / non-empty non-comment lines of that candidate. Report arithmetic mean across snippets, never total problems / total LoC. All-language PPLs unavailable because ETL/Reactions counts are not comparable."),
        ("LoC", "Strip -- and // line comments for ATL/QVT-O, // for ETL/Reactions, and /* */ block comments. Preserve quoted strings and inline code. Candidate-source denominator, not reference-source LoC."),
        ("Legacy coverage", "New frozen campaign evaluates every qualified saved T0/T1/T2 source. Equal task/context/source-hash snapshots share one execution. Every run/snapshot retains a linked result. No historical candidate-result reuse and no LLM calls."),
        ("Legacy Pass@1", "T0 behavioral full-suite passes / qualified parsable T0 candidates. Only shown when all eligible candidates have archived legacy verdicts. Incomplete observed subset is not Pass@1."),
        ("Legacy full-suite rate", "Behavioral full-suite passes / saved candidates with qualified legacy reference. Every eligible candidate is included; compilation/runtime/infrastructure errors count non-PASS and remain separate outcomes. Unqualified tasks and absent transformations remain explicitly unavailable."),
        ("Generated tests", "Original generated-suite observations and metrics retained with their own denominators. First semantic execution may include syntax repairs and is not unconditional Pass@1."),
        ("Pairs", "120 semantic-refinement pairs are a selected supplementary population. Primary, later-syntax-excluded and full-context Reactions views overlap and cannot be added."),
        ("Mutation matching", "Compare same language/task/operator. Unique generated counts union observations within the named scope; repeated rows remain separately labeled. Manual compilation/runtime errors never kill. This catalogue result is not MS_Q."),
        ("Model identities", "Group names identify the selected experimental configurations. Manifests contain stale labels for some models. Initial and snapshot-specific generation.model/provider values are retained separately; do not infer executed model versions from manifest labels."),
        ("Mixed families", "Mixed pooling describes three orchestration configurations, not one model. Individual configurations retain separate groups and generation records preserve actual recorded stage model names."),
        ("Excel diagnostics", "Long diagnostic text is shortened for Excel display with an explicit retained-in-CSV marker. The CSV files and raw logs preserve full messages. All numeric observations and identifiers remain intact."),
        ("Historical comparison", "Published GPT-5.1 FS+GR aggregates verified in arxiv:2606.25193v1 Tables 3/4/5. Published PPL definition uses candidate LoC. Local legacy CSV label gpt-5 and reference-LoC implementation differ; do not claim published raw computations reconstructed. Rounded published values have no verified exact numerator/denominator. Current behavioral-qualified suites and primary Reactions contexts limit semantic comparability; no controlled causal comparison."),
        ("Independence", "Inspected refinement prompts contain no legacy assertions. Complete initial requests and dirty historical execution states are unavailable; strict historical oracle independence is not claimed."),
        ("Archived metrics", "Canonical RQ rows were independently recomputed from selected raw artifacts and checked against the frozen CSV. Canonical files remain unchanged."),
        ("Sources", str(selection) + "; " + str(campaign) + "; " + str(full_campaign) + ". Exact input hashes in source-inventory.csv and output hashes in table-manifest.json."),
    )]
    legacy_method_rows = []
    mapping = test_mapping
    for snapshot in snapshots:
        observed_methods = full_methods_index[snapshot["legacy_evidence_job"]]
        if not observed_methods:
            observed_methods = [{"class": case["class"], "method": case["method"], "strength": case["strength"],
                "outcome": "UNAVAILABLE", "observed": False, "detail": snapshot["legacy_unavailable_reason"]}
                for case in mapping if (case["language"], case["task"]) == (snapshot["language"], snapshot["task"])]
        for method in observed_methods:
            legacy_method_rows.append({"group": snapshot["group"], "batch_id": snapshot["batch_id"],
                "run_id": snapshot["run_id"], "language": snapshot["language"], "task": snapshot["task"],
                "snapshot": snapshot["snapshot"], "iteration": snapshot["iteration"],
                "job_id": snapshot["legacy_evidence_job"], "class": method["class"], "method": method["method"],
                "strength": method["strength"], "outcome": method["outcome"], "observed": method["observed"], "detail": method["detail"]})
    for snapshot in snapshots:
        if snapshot["legacy_reference_qualified"] and snapshot["source_available"]:
            assert snapshot["legacy_outcome"] != "UNAVAILABLE"
    for row in legacy_rows:
        if row["scope_type"] == "all" and row["language"] == "ALL":
            overview.append({"metric": f"Fresh legacy {row['snapshot']} full pass (qualified saved)",
                "numerator": row["full_pass_num"], "denominator": row["full_pass_den"], "value": row["full_pass_rate"],
                "note": "Same qualified saved-source population at all three snapshots; unqualified/missing slots separate"})
            if row["snapshot"] == "T0":
                overview.append({"metric": "Fresh legacy conditional Pass@1 (qualified parsable T0)",
                    "numerator": row["pass1_num"], "denominator": row["pass1_den"], "value": row["pass1_rate"],
                    "note": "Initial candidate only; denominator differs from unconditional initial success"})
    overview.append({"metric": "Legacy test classes", "numerator": len({r["java_file"] for r in test_mapping}),
        "denominator": None, "value": None, "note": "Distinct original JUnit/Vitruv test classes in task-to-test-mapping.csv"})
    overview.append({"metric": "Legacy test methods", "numerator": len(test_mapping), "denominator": None,
        "value": None, "note": "One task-to-test-mapping.csv row per original test method"})
    tables = {"Overview": overview, "Syntax": syntax_rows, "Legacy": legacy_rows,
        "Generated": generated_rows, "Pair_summary": pair_summary, "Mutation_summary": mutation_summary,
        "Transitions": transition_rows, "Historical_GPT51": historical, "Runs": runs, "Snapshots": snapshots, "Pairs": enriched_pairs,
        "Legacy_methods": legacy_method_rows,
        "Paired_reproduction": pair_reproduction, "Execution_issues": typed(read_csv(full_campaign / "execution-issues.csv")),
        "Manual_mutants": manual_rows, "Mutant_methods": typed(read_csv(campaign / "mutants-methods.csv")),
        "Matched_unique": unique_rows, "Matched_runs": mutant_rows, "References": qualification,
        "Test_mapping": mapping, "Canonical_RQ": frozen_rq, "Readme": readme}
    tables["Configurations"] = [{"group": group.name, "selected_runs": len(group.runs),
        "batches": ", ".join(sorted({batch for batch, _ in group.runs})),
        "initial_generation_models": json.dumps(sorted({r["initial_generation_model"] for r in runs if r["group"] == group.name and r["initial_generation_model"]}), ensure_ascii=False),
        "all_transformation_generation_models": json.dumps(sorted({m for r in runs if r["group"] == group.name for m in json.loads(r["recorded_transformation_models"])}), ensure_ascii=False),
        "all_test_generation_models": json.dumps(sorted({m for r in runs if r["group"] == group.name for m in json.loads(r["recorded_test_generation_models"])}), ensure_ascii=False),
        "note": "Model strings from generation records; separate from stale manifest labels. Mixed refinement roles may differ from initial generator."} for group in groups]
    source_paths.add(campaign / "mutants-methods.csv")
    source_paths.update(full_campaign.glob("*.json"))
    source_paths.update(full_campaign.glob("*.csv"))
    source_paths.add(full_campaign / "reporting-implementation.py")
    source_paths.update((full_campaign / "implementation").rglob("*.py"))
    source_paths.update((full_campaign / "raw").rglob("complete.json"))
    source_paths.update((full_campaign / "raw").rglob("execution.json"))
    source_paths.update((full_campaign / "raw").rglob("*.xml"))
    source_paths.update(INVENTORIED_CODE)
    input_files = [p for p in sorted(source_paths) if p.is_file()]
    inputs = [{"path": repository_relative(p), "sha256": digest(p), "bytes": p.stat().st_size} for p in input_files]
    tables = portable(tables)
    output.mkdir(parents=True)
    (output / "csv").mkdir()
    for name, rows in tables.items():
        headers = list(dict.fromkeys(k for row in rows for k in row))
        with (output / "csv" / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
    with (output / "source-inventory.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "sha256", "bytes"])
        writer.writeheader()
        writer.writerows(inputs)
    (output / "tables.json").write_text(json.dumps(tables, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copyfile(Path(__file__), output / "reduce_tables.py")
    assert all(digest(p) == r["sha256"] for p, r in zip(input_files, inputs)), "input changed during reduction"
    validation = {"selected_runs": len(runs), "groups": len(groups), "tasks": 47, "saved_transformations": 487,
        "semantic_pairs": 120, "unique_mutants": 289, "run_mutant_observations": 3468,
        "canonical_rows_recomputed_and_equal": len(recomputed), "input_files_verified": len(inputs),
        "hand_calculated_loc_and_missing_data_checks": "passed",
        "paired_reproduction_outcome_mismatches": [r for r in pair_reproduction if not r["pre_outcome_identical"] or not r["post_outcome_identical"]],
        "new_maven_executions": json.loads((full_campaign / "integrity.json").read_text())["maven_executions"], "new_llm_calls": 0,
        "legacy_snapshot_evidence": {s: dict(Counter(r["legacy_evidence_kind"] for r in snapshots if r["snapshot"] == s)) for s in ("T0", "T1", "T2")}}
    validation = portable(validation)
    (output / "validation.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read-only reduction of supplementary evaluation tables")
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
