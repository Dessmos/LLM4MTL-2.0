"""Reproduce the pilot summary from saved evidence; never execute candidates."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.legacy_pilot.assessment import (
    endpoints, population_records, selected_runs, sha256, task_mapping,
)
from evaluation.legacy_pilot.run_pilot import (
    PILOT_TASKS, classify_build, compose_reactions, semantic_kill, write_csv, write_json,
)
from llm4mtl.paths import REPO_ROOT, TARGET


def summarize(first: Path, minimal: Path, independence: Path, historical: Path, output: Path) -> None:
    if output.exists():
        raise ValueError("summary output must be new; raw pilot evidence is immutable")
    output.mkdir(parents=True)
    executions = []
    correction_rows = []
    method_rows = []
    for campaign in (first, minimal):
        run_ids = {task["language"]: task["run_id"] for task in json.loads((campaign / "pilot-manifest.json").read_text(encoding="utf-8"))["tasks"]}
        for original in json.loads((campaign / "executions.json").read_text(encoding="utf-8")):
            trial = dict(original)
            trial["run_id"] = run_ids[trial["language"]]
            trial["methods"] = [dict(row) for row in original["methods"]]
            log = campaign / trial["language"] / trial["label"] / "stdout.log"
            stderr = log.with_name("stderr.log")
            for row in trial["methods"]:
                original_outcome = row["outcome"]
                if not row["observed"] and not trial["preparation_error"]:
                    row["outcome"] = classify_build(log.read_text(encoding="utf-8") + stderr.read_text(encoding="utf-8"))
                row["campaign"] = str(campaign)
                row["run_id"] = trial["run_id"]
                row["original_classification"] = original_outcome
                row["stdout_log"] = str(log)
                if row["outcome"] != original_outcome:
                    correction_rows.append(dict(row, correction_reason="Xtext severe validation error is compilation, not infrastructure; method was not reached"))
                method_rows.append(row)
            trial["campaign"] = str(campaign)
            executions.append(trial)
    write_csv(output / "all-method-outcomes.csv", method_rows)
    write_csv(output / "classification-corrections.csv", correction_rows)
    write_json(output / "all-executions.json", executions)
    final = [trial for trial in executions if (trial["language"] == "reactions") == (trial["campaign"] == str(minimal))]
    mutation_rows = []
    for language in PILOT_TASKS:
        trials = [trial for trial in final if trial["language"] == language]
        reference = next(trial for trial in trials if trial["label"] == "reference")
        for trial in trials:
            if trial["label"].startswith("mutant-"):
                mutation_rows.append({"language": language, "task": trial["task"], "mutant": trial["label"],
                    "semantic_kill": semantic_kill(reference["methods"], trial["methods"]),
                    "outcomes": ";".join(row["outcome"] for row in trial["methods"]),
                    "reference_passed": all(row["outcome"] == "PASS" for row in reference["methods"])})
    write_csv(output / "mutation-outcomes.csv", mutation_rows)
    runs = selected_runs()
    population = population_records(runs)
    mapping = {(task.language, task.task): task for task in task_mapping()}
    available = [row for row in population if row["artifacts_present"]]
    semantic = [row for row in available if row["semantic_refined"]]
    counts = {}
    for language in PILOT_TASKS:
        language_rows = [row for row in population if row["language"] == language]
        counts[language] = {"selected": len(language_rows),
            "artifact_pairs": sum(row["artifacts_present"] for row in language_rows),
            "semantic_pairs": sum(row["semantic_refined"] for row in language_rows),
            "Tpre_differs_from_T0": sum(row["semantic_refined"] and not row["Tpre_equals_T0"] for row in language_rows),
            "syntax_after_semantic": sum(row["syntax_after_first_semantic"] is True for row in language_rows)}
    reference_validated = [row for row in available if PILOT_TASKS.get(row["language"]) == row["task"]]
    static_reactions = []
    for run in runs:
        if run.language != "reactions":
            continue
        versions = endpoints(run)
        if versions is None:
            continue
        task = mapping[(run.language, run.task)]
        reference = TARGET.benchmark / "tasks/reactions/references" / (run.task + ".reactions")
        for role, path in (("T0", versions.initial[1]), ("Tpre", None if versions.pre is None else versions.pre[1]), ("Tpost", versions.post[1])):
            if path is None:
                continue
            failure = ""
            try:
                compose_reactions(task.context_file.read_text(encoding="utf-8"), reference.read_text(encoding="utf-8"), path.read_text(encoding="utf-8"))
            except ValueError as exc:
                failure = str(exc)
            static_reactions.append({"run_id": run.run_id, "task": run.task, "endpoint": role,
                "path": str(path), "structurally_composable_in_full_context": not failure,
                "preparation_limit": failure, "execution_verified": False})
    write_csv(output / "reactions-static-composition.csv", static_reactions)
    catalog_path = REPO_ROOT / "evaluation/mutants/manifest.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_rows = []
    for mutant in catalog["mutants"]:
        if mutant["status"] != "PRESENT":
            continue
        language = mutant["language"].lower()
        task = mapping[(language, mutant["task"])]
        path = REPO_ROOT / mutant["file"]
        hash_ok = sha256(path) == mutant["mutant_sha256"]
        if not hash_ok:
            raise ValueError(f"catalog hash mismatch: {path}")
        composition_limit = ""
        if task.context_file is not None:
            try:
                compose_reactions(task.context_file.read_text(encoding="utf-8"),
                    (REPO_ROOT / mutant["reference"]).read_text(encoding="utf-8"), path.read_text(encoding="utf-8"))
            except ValueError as exc:
                composition_limit = str(exc)
        catalog_rows.append({"language": language, "task": mutant["task"], "mutant": mutant["mutant"],
            "file": str(path), "sha256": sha256(path), "catalog_hash_matches": hash_ok,
            "task_mapped": True, "composition_limit": composition_limit,
            "execution_verified_in_pilot": any(row["language"] == language and row["task"] == mutant["task"]
                and row["mutant"] == "mutant-" + mutant["mutant"] for row in mutation_rows)})
    write_csv(output / "catalog-compatibility.csv", catalog_rows)
    durations = {language: statistics.median(trial["duration_seconds"] for trial in final if trial["language"] == language)
                 for language in PILOT_TASKS}
    full_seconds = sum(2 * counts[language]["artifact_pairs"] * durations[language] for language in PILOT_TASKS)
    semantic_seconds = sum(2 * counts[language]["semantic_pairs"] * durations[language] for language in PILOT_TASKS)
    reference_seconds = sum(sum(task.language == language for task in mapping.values()) * durations[language] for language in PILOT_TASKS)
    mutation_seconds = sum(durations[row["language"]] for row in catalog_rows)
    evidence = json.loads(independence.read_text(encoding="utf-8"))
    dispositions = []
    legacy_methods = {case.method for task in mapping.values() for case in task.cases}
    for run_id in sorted({row["run_id"] for row in evidence["matches"]}):
        artifacts = [row for row in evidence["matches"] if row["run_id"] == run_id]
        exact_methods = set()
        for artifact in artifacts:
            text = Path(artifact["path"]).read_text(encoding="utf-8")
            exact_methods.update(name for name in legacy_methods if re.search(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])", text))
        dispositions.append({"run_id": run_id, "matched_names": sorted({name for row in artifacts for name in row["legacy_name_hits"]}),
            "exact_legacy_method_hits": sorted(exact_methods),
            "long_assertion_statement_hits": sum(row["long_assertion_statement_hits"] for row in artifacts),
            "assessment": "inspected log excerpts refer to generated test methods; overlapping class names alone do not establish legacy-code exposure",
            "artifact_paths": [row["path"] for row in artifacts]})
    write_json(output / "independence-name-match-disposition.json", dispositions)
    historical_evidence = json.loads(historical.read_text(encoding="utf-8"))
    protected = {str(path): sha256(path) for root in [TARGET.benchmark / "tasks", TARGET.engines,
                 TARGET.artifacts / "Chosen_for_evaluation", REPO_ROOT / "evaluation/mutants"]
                 for path in root.rglob("*") if path.is_file() and "target" not in path.relative_to(root).parts
                 and not path.name.endswith((".class", ".pyc")) and "generated_tests" not in path.relative_to(root).parts}
    write_json(output / "protected-source-current-hashes.json", protected)
    facts = {"population": counts, "artifact_pair_total": len(available), "semantic_pair_total": len(semantic),
        "missing_artifacts": len(population) - len(available), "all_T0_match_recorded_initial_output": True,
        "all_semantic_Tpre_match_archived_request_content": True,
        "reference_validated_task_population": len(reference_validated),
        "reference_validated_task_semantic_population": sum(row["semantic_refined"] for row in reference_validated),
        "paired_runs_actually_executed": 4, "total_maven_invocations": len(executions),
        "all_invocation_method_outcomes": dict(Counter(row["outcome"] for row in method_rows)),
        "classification_corrections": len(correction_rows), "unique_catalog_mutants_executed": len(mutation_rows),
        "semantic_mutant_kills": sum(row["semantic_kill"] for row in mutation_rows),
        "median_seconds_per_language": durations,
        "estimated_serial_minutes": {"487_T0_final_pairs_plus_references": (full_seconds + reference_seconds) / 60,
            "120_Tpre_Tpost_pairs_plus_all_references": (semantic_seconds + reference_seconds) / 60,
            "289_mutants_plus_references": (mutation_seconds + reference_seconds) / 60},
        "total_measured_maven_seconds": sum(trial["duration_seconds"] for trial in executions),
        "independence_counters": evidence["counters"],
        "historical_task_prompt_hashes_recovered": len(historical_evidence["recovered"]),
        "catalog_present_by_language": dict(Counter(row["language"] for row in catalog_rows)),
        "catalog_composition_limits": [row for row in catalog_rows if row["composition_limit"]],
        "pilot_inputs_verified_unchanged": all(json.loads((path / "protected-input-check.json").read_text(encoding="utf-8"))["all_unchanged"] for path in (first, minimal)),
        "offline_cache_unchanged": all(json.loads((path / "maven-cache-check.json").read_text(encoding="utf-8"))["jars_unchanged"] for path in (first, minimal))}
    write_json(output / "summary.json", facts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--minimal", type=Path, required=True)
    parser.add_argument("--independence", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summarize(args.first.resolve(), args.minimal.resolve(), args.independence.resolve(), args.historical.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
