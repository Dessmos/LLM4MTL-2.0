"""Derive supplementary tables from immutable campaign observations."""

from __future__ import annotations

import argparse
import json
import shutil
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evaluation.legacy_campaign.protocol import behavioral_outcome, qualified
from evaluation.legacy_campaign.run import check_freeze, completed, fingerprint, qualification, read_json
from evaluation.legacy_pilot.assessment import sha256
from evaluation.legacy_pilot.run_pilot import write_csv, write_json
from llm4mtl.paths import REPO_ROOT, TARGET


RUNTIME_PROPERTIES = ("user.language", "user.country", "user.timezone", "file.encoding", "java.version", "java.vendor", "os.arch")


def runtime_properties(campaign: Path, job_id: str) -> dict[str, str | None]:
    reports = sorted((campaign / "raw" / job_id).glob("attempt-*/trial/reports/**/TEST-*.xml"))
    observed = []
    for report in reports:
        properties = {item.get("name"): item.get("value") for item in ET.parse(report).getroot().findall("./properties/property")}
        observed.append({key: properties.get(key) for key in RUNTIME_PROPERTIES})
    if observed and any(item != observed[0] for item in observed):
        raise ValueError(f"nonidentical runtime properties in job: {job_id}")
    return observed[0] if observed else {}


def listener_runtime_evidence(stderr: str, class_name: str, method: str) -> bool:
    """Recover an explicitly logged JUnit engine failure when Surefire lost XML."""
    return bool(re.search(r"TestExecutionListener[^\n]*\[class:[^\]]*\." + re.escape(class_name)
        + r"\]/\[method:" + re.escape(method) + r"\(\)\][^\n]*TestExecutionResult \[status = FAILED, throwable = org\.eclipse\.m2m\.atl\.engine\.emfvm\.VMException:", stderr))


def recover_listener_failures(campaign: Path, execution: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Append derived corrections; raw runner verdicts and XML remain immutable."""
    result = dict(execution, methods=[dict(row) for row in execution["methods"]])
    corrections = []
    logs = list((campaign / "raw" / execution["job"]["job_id"]).glob("attempt-*/trial/stderr.log"))
    for row in result["methods"]:
        if row["observed"] or row["outcome"] != "INFRASTRUCTURE_ERROR":
            continue
        for path in logs:
            stderr = path.read_text(encoding="utf-8")
            if listener_runtime_evidence(stderr, row["class"], row["method"]):
                corrections.append({"job_id": row["job_id"], "class": row["class"], "method": row["method"],
                    "original_outcome": row["outcome"], "original_xml_observed": False,
                    "derived_outcome": "RUNTIME_ERROR", "evidence": str(path), "evidence_sha256": sha256(path),
                    "reason": "JUnit logged this exact method FAILED with ATL VMException; Surefire listener crashed serializing that exception and produced no testcase XML. Reporting infrastructure failure remains separately documented."})
                row.update(outcome="RUNTIME_ERROR", observed=True, observation_source="JUnit listener stderr; testcase XML unavailable",
                    detail=stderr)
                break
    return result, corrections


def paired_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """All slots remain in denominators; report technical losses separately."""
    result = {"runs": len(rows), "qualified_runs": sum(row["qualified"] for row in rows)}
    for role in ("Tpre", "Tpost"):
        result[role + "_suite_pass"] = sum(row[role + "_outcome"] == "PASS" for row in rows)
        methods = [method for row in rows for method in row[role + "_methods"] if method["strength"] == "behavioral"]
        result[role + "_behavioral_methods"] = len(methods)
        result[role + "_method_pass"] = sum(method["outcome"] == "PASS" for method in methods)
        result[role + "_suite_outcomes"] = dict(Counter(row[role + "_outcome"] for row in rows))
        result[role + "_method_outcomes"] = dict(Counter(method["outcome"] for method in methods))
    result["suite_improvements"] = sum(row["Tpre_outcome"] != "PASS" and row["Tpost_outcome"] == "PASS" for row in rows)
    result["initially_nonpassing_qualified"] = sum(row["qualified"] and row["Tpre_outcome"] != "PASS" for row in rows)
    result["assertion_only_repairs"] = sum(row["Tpre_outcome"] == "ASSERTION_FAILURE" and row["Tpost_outcome"] == "PASS" for row in rows)
    result["initial_assertion_failures"] = sum(row["Tpre_outcome"] == "ASSERTION_FAILURE" for row in rows)
    result["technical_recoveries"] = sum(row["Tpre_outcome"] in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR")
        and row["Tpost_outcome"] == "PASS" for row in rows)
    result["suite_regressions"] = sum(row["Tpre_outcome"] == "PASS" and row["Tpost_outcome"] != "PASS" for row in rows)
    result["method_improvements"] = result["method_losses"] = result["assertion_regressions"] = result["technical_losses"] = 0
    for row in rows:
        before = {method["method"]: method for method in row["Tpre_methods"] if method["strength"] == "behavioral"}
        after = {method["method"]: method for method in row["Tpost_methods"] if method["strength"] == "behavioral"}
        if before.keys() != after.keys():
            raise ValueError(f"nonidentical paired method identities: {row['run_id']}")
        for name, method in before.items():
            a, b = method["outcome"], after[name]["outcome"]
            result["method_improvements"] += a != "PASS" and b == "PASS"
            result["method_losses"] += a == "PASS" and b != "PASS"
            result["assertion_regressions"] += a == "PASS" and b == "ASSERTION_FAILURE"
            result["technical_losses"] += a == "PASS" and b in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR")
    return result


def matched_class(manual: str, generated: list[dict[str, Any]]) -> tuple[str, str]:
    valid = [row for row in generated if row["reference_result"] == "PASS" and row["generated_outcome"] in ("KILLED", "SURVIVED")]
    if manual not in ("KILLED", "SURVIVED"):
        return "UNINTERPRETABLE", "manual " + manual
    if not valid:
        return "UNMATCHED", "no interpretable generated observation"
    killed = any(row["generated_outcome"] == "KILLED" for row in valid)
    return ("BOTH" if killed and manual == "KILLED" else "GENERATED_ONLY" if killed else
            "MANUAL_ONLY" if manual == "KILLED" else "NEITHER"), ""


def grouped_unique_matches(rows: list[dict[str, Any]], group_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    result = []
    for key, members in sorted(groups.items()):
        counts = Counter(row["match_class"] for row in members)
        result.append({**dict(zip(group_fields, key)), "catalogue": len(members),
            "manual_outcomes": json.dumps(dict(Counter(row["manual_outcome"] for row in members)), sort_keys=True),
            "comparable_unique": sum(counts[name] for name in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER")),
            **{name: counts[name] for name in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER", "UNINTERPRETABLE", "UNMATCHED")}})
    return result


def grouped_run_observations(rows: list[dict[str, Any]], group_field: str) -> list[dict[str, Any]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row[group_field]].append(row)
    result = []
    for key, members in sorted(groups.items()):
        unique = defaultdict(list)
        for row in members:
            unique[(row["language"], row["task"], row["operator"])].append(row)
        unique_counts = Counter(matched_class(items[0]["manual_outcome"], items)[0] for items in unique.values())
        result.append({group_field: key, "selected_runs": len({row["run_id"] for row in members}),
            "unique_identities": len(unique), "run_mutant_observations": len(members),
            "generated_interpretable_observations": sum(row["reference_result"] == "PASS" and row["generated_outcome"] in ("KILLED", "SURVIVED") for row in members),
            "comparable_unique": sum(unique_counts[name] for name in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER")),
            "unique_match_counts": json.dumps(dict(unique_counts), sort_keys=True),
            "repeated_match_counts": json.dumps(dict(Counter(row["match_class"] for row in members)), sort_keys=True)})
    return result


def table(headers: list[str], rows: list[list[Any]]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
        + ["| " + " | ".join(str(value) for value in row) + " |" for row in rows])


def summarize(output: Path, destination: Path, dependency_controls: Path) -> None:
    if destination.exists():
        raise ValueError("report destination must be new; earlier reports are preserved")
    frozen = check_freeze(output)
    controls = qualification(output, frozen)
    extra = read_json(dependency_controls / "freeze.json")
    if extra["parent_freeze"] != frozen["freeze_sha256"] or fingerprint({key: value for key, value in extra.items() if key != "freeze_sha256"}) != extra["freeze_sha256"]:
        raise ValueError("dependency control freeze changed")
    extra_facts = [completed(dependency_controls, job, extra["freeze_sha256"]) for job in extra["jobs"]]
    if any(fact is None for fact in extra_facts):
        raise ValueError("dependency controls unfinished")
    for control in controls:
        if control["language"] != "reactions":
            continue
        negative = next(fact for fact in extra_facts if fact["job"]["role"] == "negative"
            and fact["job"]["task"] == control["task"] and fact["job"]["context"] == control["context"])
        control["negative_methods"] = negative["methods"]
        control["qualified"] = qualified(control["methods"], negative["methods"])
        if not control["qualified"] and control["reference_behavioral_outcome"] == "PASS":
            control["reason"] = "behavioral suite still passes after target reaction removed: masked by fixed background logic"
    qualified_index = {(row["language"], row["task"], row["context"]): row for row in controls}
    facts = {job["job_id"]: completed(output, job, frozen["freeze_sha256"]) for job in frozen["jobs"]}
    if any(value is None for value in facts.values()):
        raise ValueError("campaign has unfinished jobs")
    corrections = []
    environments = []
    for job_id, fact in facts.items():
        recovered, adjustments = recover_listener_failures(output, fact)
        facts[job_id] = recovered
        corrections.extend(adjustments)
        properties = runtime_properties(output, job_id)
        if properties:
            environments.append({"job_id": job_id, **properties})
    jobs = frozen["jobs"]
    pair_rows = []
    mismatches = []
    for pair in frozen["pairs"]:
        for context in ("primary", "full") if pair["language"] == "reactions" else ("primary",):
            executions = {}
            for role in ("Tpre", "Tpost"):
                job = next(job for job in jobs if job["phase"] == "pairs" and job["run_id"] == pair["run_id"]
                    and job["context"] == context and job["role"] == role)
                executions[role] = facts[job["job_id"]]
            a, b = executions["Tpre"], executions["Tpost"]
            if a["fixed_inputs_digest"] and b["fixed_inputs_digest"] and a["fixed_inputs_digest"] != b["fixed_inputs_digest"]:
                mismatches.append({"run_id": pair["run_id"], "context": context, "reason": "fixed inputs differ"})
            if a["runtime_dependencies"] and b["runtime_dependencies"] and a["runtime_dependencies"] != b["runtime_dependencies"]:
                mismatches.append({"run_id": pair["run_id"], "context": context, "reason": "runtime dependency classpaths differ"})
            a_environment = runtime_properties(output, a["job"]["job_id"])
            b_environment = runtime_properties(output, b["job"]["job_id"])
            if a_environment and b_environment and a_environment != b_environment:
                mismatches.append({"run_id": pair["run_id"], "context": context, "reason": "Surefire JVM configuration differs"})
            reference_job = next(job for job in jobs if job["phase"] == "references" and job["role"] == "reference"
                and job["language"] == pair["language"] and job["task"] == pair["task"] and job["context"] == context)
            reference_facts = facts[reference_job["job_id"]]
            for endpoint in (a, b):
                if endpoint["fixed_inputs_digest"] and endpoint["fixed_inputs_digest"] != reference_facts["fixed_inputs_digest"]:
                    mismatches.append({"run_id": pair["run_id"], "context": context, "reason": "fixtures/templates differ from reference control"})
                if endpoint["runtime_dependencies"] and endpoint["runtime_dependencies"] != reference_facts["runtime_dependencies"]:
                    mismatches.append({"run_id": pair["run_id"], "context": context, "reason": "runtime dependencies differ from reference control"})
            manifest = read_json(Path(pair["manifest"]))
            control = qualified_index[(pair["language"], pair["task"], context)]
            row = {"run_id": pair["run_id"], "language": pair["language"], "task": pair["task"], "context": context,
                "qualified": control["qualified"], "qualification_reason": control["reason"],
                "transformation_model": manifest["transformation_model"], "test_generation_model": manifest["test_generation_model"],
                "syntax_sensitivity_exclusion": pair["syntax_sensitivity_exclusion"],
                "final_semantically_evaluated": pair["final_semantically_evaluated"],
                "Tpre_iteration": pair["Tpre_iteration"], "Tpost_iteration": pair["Tpost_iteration"],
                "Tpre_source": pair["Tpre"], "Tpost_source": pair["Tpost"],
                "fixed_inputs_identical": None if not a["fixed_inputs_digest"] or not b["fixed_inputs_digest"] else a["fixed_inputs_digest"] == b["fixed_inputs_digest"],
                "Tpre_outcome": behavioral_outcome(a["methods"]), "Tpost_outcome": behavioral_outcome(b["methods"]),
                "Tpre_methods": a["methods"], "Tpost_methods": b["methods"]}
            pair_rows.append(row)
    if mismatches:
        raise ValueError(f"paired environment integrity failed: {mismatches}")
    primary = [row for row in pair_rows if row["context"] == "primary"]
    if len(primary) != 120 or len({row["run_id"] for row in primary}) != 120:
        raise ValueError("paired population overlap")
    metrics = []
    for population in ("all_selected", "qualified", "no_later_syntax", "qualified_no_later_syntax", "full_reactions"):
        source = [row for row in pair_rows if row["context"] == "full"] if population == "full_reactions" else primary
        if population.startswith("qualified"):
            source = [row for row in source if row["qualified"]]
        if "no_later_syntax" in population:
            source = [row for row in source if not row["syntax_sensitivity_exclusion"]]
        for language in ("all", "atl", "etl", "qvto", "reactions"):
            subset = source if language == "all" else [row for row in source if row["language"] == language]
            if subset:
                metrics.append({"population": population, "language": language, "task": "all", **paired_metrics(subset)})
    for language, task in sorted({(row["language"], row["task"]) for row in primary}):
        subset = [row for row in primary if (row["language"], row["task"]) == (language, task)]
        metrics.append({"population": "all_selected", "language": language, "task": task, **paired_metrics(subset)})
    manual = []
    for mutant in frozen["mutants"]:
        job = next(job for job in jobs if job["phase"] == "mutants" and job["language"] == mutant["language"]
            and job["task"] == mutant["task"] and job["operator"] == mutant["mutant"])
        execution = facts[job["job_id"]]
        outcome = behavioral_outcome(execution["methods"])
        outcome = {"PASS": "SURVIVED", "ASSERTION_FAILURE": "KILLED"}.get(outcome, outcome)
        manual.append({"language": mutant["language"], "task": mutant["task"], "operator": mutant["mutant"],
            "category": mutant["category"], "source": mutant["source"], "sha256": mutant["mutant_sha256"],
            "manual_outcome": outcome, "reason": execution.get("unavailable_reason", ""), "job_id": job["job_id"],
            "behavioral_assertion_witnesses": ";".join(row["method"] for row in execution["methods"] if row["strength"] == "behavioral" and row["outcome"] == "ASSERTION_FAILURE"),
            "reference_qualified": qualified_index[(mutant["language"], mutant["task"], "primary")]["qualified"]})
    generated = []
    manual_index = {(row["language"], row["task"], row["operator"]): row for row in manual}
    for matrix in frozen["generated_matrix_rows"]:
        manifest = read_json(TARGET.run_dir(matrix["batch_id"], matrix["run_id"]) / "manifest.json")
        for operator in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"):
            identity = (matrix["language"], matrix["task"], operator)
            if identity not in manual_index:
                if matrix[operator] != "N/A":
                    raise ValueError(f"generated identity missing from existing catalogue: {identity}")
                continue
            if matrix[operator] == "N/A":
                raise ValueError(f"generated N/A conflicts with existing PRESENT mutant: {identity}")
            baseline = manual_index[identity]
            generated.append({"run_id": matrix["run_id"], "language": identity[0], "task": identity[1],
                "operator": operator, "reference_result": matrix["reference_result"], "generated_outcome": matrix[operator],
                "manual_outcome": baseline["manual_outcome"], "artifact": matrix["artifact"], "csv_line": matrix["csv_line"],
                "evaluation_group": Path(matrix["artifact"]).parent.name,
                "configured_transformation_model": manifest["transformation_model"],
                "configured_test_generation_model": manifest["test_generation_model"]})
    if len(generated) != 12 * 289 or len({(row["run_id"], row["operator"]) for row in generated}) != len(generated):
        raise ValueError("generated repeated-observation population overlaps or is incomplete")
    by_identity = defaultdict(list)
    for row in generated:
        by_identity[(row["language"], row["task"], row["operator"])].append(row)
        category, reason = matched_class(row["manual_outcome"], [row])
        row["match_class"], row["uninterpretable_reason"] = category, reason
    matches = []
    for row in manual:
        observations = by_identity[(row["language"], row["task"], row["operator"])]
        category, reason = matched_class(row["manual_outcome"], observations)
        matches.append(dict(row, match_class=category, unmatched_reason=reason,
            generated_observations=len(observations), generated_valid=sum(item["reference_result"] == "PASS"
                and item["generated_outcome"] in ("KILLED", "SURVIVED") for item in observations),
            generated_killed=sum(item["reference_result"] == "PASS" and item["generated_outcome"] == "KILLED" for item in observations),
            generated_technical=sum(item["generated_outcome"] in ("ERROR", "PARSE_FAILED") for item in observations),
            generated_not_judged=sum(item["generated_outcome"] == "NOT_JUDGED" for item in observations)))
    mutation_metrics = []
    for language in ("all", "atl", "etl", "qvto", "reactions"):
        subset = matches if language == "all" else [row for row in matches if row["language"] == language]
        counts = Counter(row["match_class"] for row in subset)
        mutation_metrics.append({"language": language, "catalogue": len(subset),
            "manual_outcomes": dict(Counter(row["manual_outcome"] for row in subset)),
            "comparable_unique": sum(counts[key] for key in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER")),
            "match_classes": dict(counts), "generated_valid_observations": sum(row["generated_valid"] for row in subset)})
    destination.mkdir(parents=True)
    write_json(destination / "reference-qualification-verified.json", controls)
    write_csv(destination / "reference-qualification-verified.csv", [{key: value for key, value in row.items() if key not in ("methods", "negative_methods")} for row in controls])
    write_json(destination / "classification-corrections.json", corrections)
    if corrections:
        write_csv(destination / "classification-corrections.csv", corrections)
    write_csv(destination / "runtime-environments.csv", environments)
    write_json(destination / "pairs.json", pair_rows)
    write_csv(destination / "pairs.csv", [{key: value for key, value in row.items() if not key.endswith("_methods")} for row in pair_rows])
    write_json(destination / "paired-metrics.json", metrics)
    write_csv(destination / "paired-metrics.csv", [{key: json.dumps(value, sort_keys=True) if isinstance(value, dict) else value for key, value in row.items()} for row in metrics])
    write_csv(destination / "manual-mutants.csv", manual)
    write_csv(destination / "unique-mutant-matches.csv", matches)
    write_csv(destination / "run-mutant-matches.csv", generated)
    write_csv(destination / "mutation-by-task.csv", grouped_unique_matches(matches, ("language", "task")))
    write_csv(destination / "mutation-by-operator.csv", grouped_unique_matches(matches, ("operator",)))
    write_csv(destination / "mutation-by-language-operator.csv", grouped_unique_matches(matches, ("language", "operator")))
    write_csv(destination / "mutation-by-evaluation-group.csv", grouped_run_observations(generated, "evaluation_group"))
    write_csv(destination / "mutation-by-configured-test-model.csv", grouped_run_observations(generated, "configured_test_generation_model"))
    write_json(destination / "derived-method-outcomes.json", [row for fact in facts.values() for row in fact["methods"]])
    write_csv(destination / "derived-method-outcomes.csv", [{**row, "observation_source": row.get("observation_source", "Surefire testcase XML" if row["observed"] else "unobserved; see raw execution evidence")} for fact in facts.values() for row in fact["methods"]])
    write_json(destination / "mutation-metrics.json", mutation_metrics)
    reference_primary = [row for row in controls if row["context"] == "primary"]
    reference_methods = [method for row in reference_primary for method in row["methods"]]
    summary = {"freeze_sha256": frozen["freeze_sha256"], "reference_qualified": sum(row["qualified"] for row in reference_primary),
        "reference_tasks": len(reference_primary), "pairs": len(primary), "paired_metrics": metrics,
        "reference_methods": len(reference_methods), "reference_method_pass": sum(row["outcome"] == "PASS" for row in reference_methods),
        "reference_behavioral_methods": sum(row["strength"] == "behavioral" for row in reference_methods),
        "reference_behavioral_method_pass": sum(row["strength"] == "behavioral" and row["outcome"] == "PASS" for row in reference_methods),
        "mutation_metrics": mutation_metrics, "manual_outcomes": dict(Counter(row["manual_outcome"] for row in manual)),
        "generated_outcomes": dict(Counter(row["generated_outcome"] for row in generated)),
        "generated_unique_identities": len(by_identity), "generated_run_mutant_observations": len(generated),
        "manual_qualified_reference_mutants": sum(row["reference_qualified"] for row in manual),
        "mixed_assertion_and_technical_mutants": [row for row in manual if row["behavioral_assertion_witnesses"] and row["manual_outcome"] not in ("KILLED", "SURVIVED")],
        "run_mutant_matches": dict(Counter(row["match_class"] for row in generated)),
        "excluded_original_attempts": [row["run_id"] for row in frozen["excluded_generated_attempts"]],
        "pair_environment_mismatches": mismatches,
        "full_context_reference_pass": sum(row["reference_behavioral_outcome"] == "PASS" for row in controls if row["context"] == "full"),
        "full_context_qualified": sum(row["qualified"] for row in controls if row["context"] == "full"),
        "full_context_masked_tasks": [row["task"] for row in controls if row["context"] == "full" and not row["qualified"] and row["reference_behavioral_outcome"] == "PASS"],
        "classification_corrections": corrections,
        "runtime_environment_profiles": list({tuple(item[key] for key in RUNTIME_PROPERTIES) for item in environments}),
        "dependency_control_jobs": len(extra_facts), "dependency_control_maven_executions": sum("command" in item for item in extra_facts),
        "executed_jobs": sum("command" in item for item in facts.values()),
        "recorded_jobs": len(facts), "maven_seconds": sum(item["duration_seconds"] for item in facts.values()),
        "reporter_sha256": sha256(Path(__file__)), "integrity": read_json(output / "integrity.json")}
    write_json(destination / "summary.json", summary)
    shutil.copy2(Path(__file__), destination / "reporter.py")
    language_rows = [row for row in metrics if row["population"] == "all_selected" and row["task"] == "all"]
    paired_table = table(["Language", "Runs (qualified)", "Tpre full suite", "Tpost full suite", "Tpre methods", "Tpost methods", "Gains / losses"], [
        [row["language"], f"{row['runs']} ({row['qualified_runs']})", f"{row['Tpre_suite_pass']}/{row['runs']}",
         f"{row['Tpost_suite_pass']}/{row['runs']}", f"{row['Tpre_method_pass']}/{row['Tpre_behavioral_methods']}",
         f"{row['Tpost_method_pass']}/{row['Tpost_behavioral_methods']}", f"{row['suite_improvements']} / {row['suite_regressions']}"] for row in language_rows])
    mutant_table = table(["Language", "Catalogue", "Killed", "Survived", "Runtime", "Unavailable", "Comparable", "Both / generated only / manual only / neither"], [
        [row["language"], row["catalogue"], row["manual_outcomes"].get("KILLED", 0), row["manual_outcomes"].get("SURVIVED", 0),
         row["manual_outcomes"].get("RUNTIME_ERROR", 0), row["manual_outcomes"].get("UNAVAILABLE", 0), row["comparable_unique"],
         " / ".join(str(row["match_classes"].get(key, 0)) for key in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER"))] for row in mutation_metrics])
    overall = next(row for row in language_rows if row["language"] == "all")
    sensitivity = next(row for row in metrics if row["population"] == "no_later_syntax" and row["language"] == "all" and row["task"] == "all")
    full_reactions = next(row for row in metrics if row["population"] == "full_reactions" and row["language"] == "all")
    task_table = table(["Language", "Task", "Runs", "Tpre behavioral suite PASS", "Tpost behavioral suite PASS"], [
        [row["language"], row["task"], row["runs"], row["Tpre_suite_pass"], row["Tpost_suite_pass"]]
        for row in metrics if row["population"] == "all_selected" and row["task"] != "all"])
    sensitivity_text = (f"Excluding the three later-syntax runs: {sensitivity['Tpre_suite_pass']}/{sensitivity['runs']} → {sensitivity['Tpost_suite_pass']}/{sensitivity['runs']} full behavioral suites; "
        f"{sensitivity['Tpre_method_pass']}/{sensitivity['Tpre_behavioral_methods']} → {sensitivity['Tpost_method_pass']}/{sensitivity['Tpost_behavioral_methods']} behavioral method slots; "
        f"{sensitivity['suite_improvements']}/{sensitivity['initially_nonpassing_qualified']} nonpassing suites recovered, including {sensitivity['assertion_only_repairs']}/{sensitivity['initial_assertion_failures']} assertion-failing suites. "
        f"Full-context Reactions integration: {full_reactions['Tpre_suite_pass']}/{full_reactions['runs']} → {full_reactions['Tpost_suite_pass']}/{full_reactions['runs']}; "
        f"Tpost retains {full_reactions['Tpost_suite_outcomes'].get('COMPILATION_ERROR', 0)} compilation failures and {full_reactions['Tpost_suite_outcomes'].get('ASSERTION_FAILURE', 0)} assertion failures.")
    excluded_syntax = [pair["run_id"] for pair in frozen["pairs"] if pair["syntax_sensitivity_exclusion"]]
    not_evaluated = [pair["run_id"] for pair in frozen["pairs"] if not pair["final_semantically_evaluated"]]
    unmatched_rows = [row for row in matches if row["match_class"] == "UNMATCHED"]
    manual_counts = summary["manual_outcomes"]
    unique_counts = mutation_metrics[0]["match_classes"]
    comparable_unique = mutation_metrics[0]["comparable_unique"]
    both = unique_counts.get("BOTH", 0)
    generated_only = unique_counts.get("GENERATED_ONLY", 0)
    manual_only = unique_counts.get("MANUAL_ONLY", 0)
    neither = unique_counts.get("NEITHER", 0)
    repeated = summary["run_mutant_matches"]
    repeated_comparable = sum(repeated.get(key, 0) for key in ("BOTH", "GENERATED_ONLY", "MANUAL_ONLY", "NEITHER"))
    generated_counts = summary["generated_outcomes"]
    lines = ["# Supplementary legacy-suite evaluation\n", "This evaluates archived Tpre/Tpost artifacts and the existing mutation catalogue; it supplements the frozen generated-suite RQ3/RQ4 measurements. No optional T0 comparison was executed.\n",
        f"Reference qualification: {summary['reference_qualified']}/47 primary task configurations. Reactions full reference passes: {summary['full_context_reference_pass']}/12, but target-dependent qualified full contexts: {summary['full_context_qualified']}/12. Exact assertions and fixtures remain unchanged.\n",
        f"Primary reference method outcomes: {summary['reference_method_pass']}/{summary['reference_methods']} PASS, including {summary['reference_behavioral_method_pass']}/{summary['reference_behavioral_methods']} behavioral methods. Smoke/weak methods do not qualify a behavioral oracle.\n",
        "## Paired behavioral results\n", paired_table, "\nSuite denominators above retain all selected runs, including UNAVAILABLE endpoints. Qualified and no-later-syntax populations, task rows and separate full-context Reactions evidence are in paired-metrics.csv. Technical recoveries are distinguished from assertion-only repairs.\n",
        f"Full-suite gains: {overall['suite_improvements']}/{overall['initially_nonpassing_qualified']} initially nonpassing qualified pairs, including {overall['assertion_only_repairs']}/{overall['initial_assertion_failures']} observed assertion repairs and {overall['technical_recoveries']} technical recoveries. Suite losses: {overall['suite_regressions']}/{overall['Tpre_suite_pass']} initially passing suites; behavioral method losses: {overall['method_losses']}/{overall['Tpre_method_pass']} initially passing method slots.\n",
        f"Tpre suite outcomes: {json.dumps(overall['Tpre_suite_outcomes'], sort_keys=True)}. Tpost suite outcomes: {json.dumps(overall['Tpost_suite_outcomes'], sort_keys=True)}.\n",
        sensitivity_text + "\n", "Later-syntax run IDs: " + "; ".join(excluded_syntax) + ".\n",
        "Adopted Tpost without historical semantic execution: " + "; ".join(not_evaluated) + ".\n",
        "## Task-level paired results\n", task_table,
        "## Existing mutation catalogue\n", mutant_table,
        "\nManual KILLED requires an executable, reference-passing behavioral assertion failure; compilation/runtime/infrastructure failures are separate. This is an unqualified catalogue detection assessment, not MS_Q.\n",
        "The unique matched denominator includes manual KILLED/SURVIVED mutants having at least one selected reference-passing generated KILLED/SURVIVED observation. Generated unique detection is the union across up to 12 opportunities per mutant. Run-mutant repeats are preserved but are not independent unique mutants. This is a descriptive archived-label comparison, with unequal test budgets and contexts.\n",
        f"Manual disposition: {len(manual)} catalogue entries = {summary['manual_qualified_reference_mutants']} qualified-reference executions + {manual_counts.get('UNAVAILABLE', 0)} unavailable entries; {summary['manual_qualified_reference_mutants']} = {manual_counts.get('KILLED', 0)} assertion kills + {manual_counts.get('SURVIVED', 0)} survivors + {manual_counts.get('RUNTIME_ERROR', 0)} runtime failures. Compilation failures: {manual_counts.get('COMPILATION_ERROR', 0)}; infrastructure failures: {manual_counts.get('INFRASTRUCTURE_ERROR', 0)}. Neither survivors nor unavailable entries are declarations of semantic equivalence.\n",
        f"Matched unique population: {comparable_unique} = {both} both + {generated_only} generated-only + {manual_only} manual-only + {neither} neither. Outside it: {unique_counts.get('UNMATCHED', 0)} unmatched + {unique_counts.get('UNINTERPRETABLE', 0)} uninterpretable ({manual_counts.get('RUNTIME_ERROR', 0)} manual runtime failures and {manual_counts.get('UNAVAILABLE', 0)} unavailable controls). Generated union detects {both + generated_only}/{comparable_unique}; manual detects {both + manual_only}/{comparable_unique}. These fractions are descriptive conditional detection proportions, not MS_Q or an equal-budget performance comparison.\n",
        "Unmatched identities: " + "; ".join(f"{row['language']}/{row['task']}/{row['operator']} (manual {row['manual_outcome']}; no valid generated observation)" for row in unmatched_rows) + ".\n",
        f"Generated observations: {len(generated)} = {generated_counts.get('KILLED', 0)} KILLED + {generated_counts.get('SURVIVED', 0)} SURVIVED + {generated_counts.get('ERROR', 0)} ERROR + {generated_counts.get('NOT_JUDGED', 0)} NOT_JUDGED, across {len(manual)} identities × {len(generated) // len(manual)} selected runs per task. Comparable run–mutant observations: {repeated_comparable} = {repeated.get('BOTH', 0)} both + {repeated.get('GENERATED_ONLY', 0)} generated-only + {repeated.get('MANUAL_ONLY', 0)} manual-only + {repeated.get('NEITHER', 0)} neither. The unique generated union is a different unit from per-run manual-only detections because other selected suites may detect those mutants. The {len(summary['excluded_original_attempts'])} original failed attempts are excluded before any language, operator, model or overall aggregation.\n",
        "## Limitations\n",
        "- Original matrix CSVs do not preserve per-invocation source hashes or method-level failure evidence. Current mutant bytes match the catalogue hashes and identities, but historical source identity and assertion attribution cannot be independently recertified from CSV labels alone.",
        "- Historical offline generated-mutation execution environment is not recoverable from the matrix CSVs. The new legacy environment is documented and controlled internally; strict historical environment equivalence between the two methods is not established.",
        "- Reactions task-specific fixed contexts establish narrower evidence than full application integration. Full-context endpoint results are a separate sensitivity population.",
        "- FamiliesToPersons_DeletedFamily and NetworkToGraph_ComponentRenamed pass in full context even after removing the target reaction; background logic masks those candidates. Their 11 mutants cannot receive valid candidate-specific legacy verdicts. AmaltheaToAscet_TaskDeleted fails both reference contexts, excluding its five mutants.",
        "- One adopted Tpost ended with SYNTAX_INVALID and lacks an archived semantic execution; it remains in the population.",
        "- Three runs include syntax refinement after semantic refinement. Their exclusion sensitivity is reported separately; differences cannot be attributed solely to semantic feedback.",
        "- Legacy behavior assertions vary in strength and cover limited scenarios. Ten QVT-O resource smoke and ten execution smoke methods, plus one Reactions source-only weak method, do not contribute to behavioral success or semantic kills.",
        "- Inspected refinement prompts contained no original assertions, but complete initial requests and historical dirty execution states were unavailable. Strict historical oracle independence is not established.",
        "- Model group labels are the configured test_generation_model strings recorded in manifests; they do not independently verify historical provider identity or the model used for later test refinement.",
        "- MAVEN_OPTS requests English locale for the Maven parent, but observed Surefire JVMs use user.language=ru, user.country=DE, user.timezone=UTC, UTF-8 and JDK 17.0.19. These actual properties are audited across pairs and recorded; an English child-JVM locale is not claimed.",
        "- Derived classification corrections recover explicitly logged JUnit ATL VMException failures when Surefire's listener failed to write testcase XML. Original INFRASTRUCTURE_ERROR labels and the reporting failure remain preserved; no Maven success without testcase evidence is counted as a pass.",
        "\n## Provenance and integrity\n", f"Freeze SHA-256: `{frozen['freeze_sha256']}`. {summary['recorded_jobs']} immutable job results; {summary['executed_jobs']} Maven invocations; {summary['maven_seconds']:.1f} accumulated Maven seconds. Protected input check: {summary['integrity']['protected_files']} files, {len(summary['integrity']['protected_mismatches'])} changes.\n",
        "Exact run IDs, source paths, hashes, adopted/evaluated facts and requests: ../paired-population.json. Original code/fixtures/context/cache hashes: ../freeze.json and ../protected-inputs.json. Method evidence: ../references-methods.csv, ../pairs-methods.csv, ../mutants-methods.csv and ../raw/. Derived method corrections are in classification-corrections.csv. No unsuccessful candidates were omitted. Offline cache and all protected source inputs are archived in ../offline-maven-repository.tar.gz and ../reproduction-inputs.tar.gz. Additional frozen target-dependency controls are preserved in ../../dependency-controls-20261008-v1/.\n"]
    (destination / "report.md").write_text("\n".join(lines), encoding="utf-8")
    mutation_all = mutation_metrics[0]
    thesis = ["# Proposed Evaluation chapter addition\n",
        "## Supplementary legacy-suite assessment (RQ3)\n",
        f"We additionally evaluated the 120 transformations entering semantic transformation refinement against the surviving original LLM4MTLs legacy tests. Tpre is the artifact supplied to the first semantic repair, whereas Tpost is the final adopted artifact. The existing 564-run generated-suite measurements remain unchanged. Reference qualification succeeded for {summary['reference_qualified']}/47 task configurations; configurations failing qualification were retained as unavailable, rather than repaired or silently removed.\n",
        paired_table,
        f"\nBehavioral full-suite success changed from {overall['Tpre_suite_pass']}/{overall['runs']} to {overall['Tpost_suite_pass']}/{overall['runs']}. There were {overall['suite_improvements']} full-suite gains and {overall['suite_regressions']} losses. Of the gains, {overall['assertion_only_repairs']} repaired observable assertion failures and {overall['technical_recoveries']} recovered from technical failures. These observations support a supplementary before/after comparison, rather than a causal estimate of semantic refinement alone.\n",
        sensitivity_text + "\n",
        "## Legacy manual mutation baseline (RQ4)\n",
        f"The unchanged 289-mutant catalogue was assessed with qualified legacy behavioral suites. The matched comparison contains {mutation_all['comparable_unique']} unique task–mutant identities. Generated-suite detection is aggregated across repeated selected observations and therefore has multiple detection opportunities. Compilation/runtime errors are not semantic kills, and the catalogue result is not a qualified mutation score MS_Q.\n",
        mutant_table,
        f"\nOn the {comparable_unique} comparable unique identities, both methods detected {both}, generated suites alone detected {generated_only}, legacy suites alone detected {manual_only}, and neither detected {neither}. Generated detection is a union over repeated opportunities. {unique_counts.get('UNMATCHED', 0)} identities lack an interpretable generated counterpart; {unique_counts.get('UNINTERPRETABLE', 0)} lack an interpretable manual counterpart. The new legacy campaign and archived generated matrix do not establish historical environment equivalence.\n",
        "\nReport the no-later-syntax sensitivity and full-context Reactions outcomes from paired-metrics.csv alongside these tables. Disclose unqualified reference configurations, all technical/unavailable outcomes, limited legacy oracle strength, unequal generated detection opportunities, absent historical request/dirty-state evidence, and unavailable historical per-mutant hashes. Strict historical oracle independence and causal attribution are not claimed.\n"]
    (destination / "thesis-additions.md").write_text("\n".join(thesis), encoding="utf-8")
    print(json.dumps({"report": str(destination / "report.md"), "summary": str(destination / "summary.json"),
        "manual": summary["manual_outcomes"], "unique_matching": mutation_all}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--controls", type=Path, required=True)
    arguments = parser.parse_args()
    summarize(arguments.output.resolve(), arguments.report.resolve(), arguments.controls.resolve())


if __name__ == "__main__":
    main()
