"""Frozen, resumable T0/T1/T2 legacy assessment, separate from canonical metrics.

The supplementary protocol is saved before execution. Original Java assertions,
fixtures, references, mutants and historical run directories remain read-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tarfile
import tempfile
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluation.legacy_campaign.execution import execute
from evaluation.legacy_campaign.protocol import behavioral_outcome, minimal_context, qualified, reference_path, with_context
from evaluation.legacy_campaign.report import recover_listener_failures, runtime_properties
from evaluation.legacy_campaign.run import check_freeze, completed, fingerprint, unavailable
from evaluation.legacy_pilot.assessment import endpoints, mapping_records, selected_runs, sha256, task_mapping
from evaluation.legacy_pilot.run_pilot import compose_reactions, write_csv, write_json
from llm4mtl.paths import REPO_ROOT, TARGET


PROTOCOL = {
    "schema_version": "supplementary-legacy-snapshots-1.0",
    "population": "Exactly 564 selected runs in 12 groups. All 487 saved transformations, including initially unparsed candidates; the 77 absent transformations remain explicit UNAVAILABLE slots.",
    "snapshots": "T0=initial iteration-000. T1=input to the first semantic transformation refinement; if none, last saved version after any syntax refinement. T2=last adopted saved iteration verified against terminal result.json. Later syntax repairs are labeled separately.",
    "suite": "Original mapped behavioral legacy methods. Smoke and weak assertions are preserved at method level but excluded from behavioral success. Reactions uses the previously specified task-specific fixed contexts, not a claim of full integration.",
    "qualification": "Fresh reference controls for all 47 tasks; Reactions target-absent controls remove only the target reaction from reference-composed context, retaining routines. No reference or assertion is repaired. Unqualified configurations produce explicit UNAVAILABLE candidate slots.",
    "deduplication": "Before execution, snapshots with the same language/task/context/source SHA-256 share one job. All run and snapshot identities retain their own linked outcome. No cross-task reuse, outcome-seeking retries or historical candidate-result reuse.",
    "pass1_conditional": "T0 behavioral full-suite passes / all initially parsable T0 candidates in qualified task configurations, with technical errors counted non-PASS. This is a supplementary definition; original-paper denominator must be checked separately.",
    "initial_unconditional": "T0 behavioral full-suite passes / all saved T0 candidates in qualified task configurations. Unparsed/technical candidates stay in the denominator. Also report all-selected and all-saved rates with unqualified/missing slots visible.",
    "full_suite": "All mapped behavioral methods observed PASS. Compilation, runtime, infrastructure and unavailable outcomes stay distinct, never silently excluded.",
    "transitions": "Same qualified task configurations and the same saved-source population at T0/T1/T2. Report PASS/PASS, non-PASS/PASS, PASS/non-PASS and non-PASS/non-PASS, splitting assertion failure and technical outcomes.",
    "syntax": "Use the immutable historical parser verdict at each exact snapshot. Unparsed Rate=failed parser verdicts/observed parser verdicts. Mean PPLs is the mean of per-candidate problem_count/non-comment-non-empty candidate LoC, only for comparable counts; ETL/Reactions unavailable.",
    "environment": "Offline Maven; isolated engine templates and a verified extracted copy of the previously frozen Maven cache. Capture actual child JVM properties. Compare fixed inputs and observed runtime dependency hashes with fresh reference controls.",
    "independence": "Inspected refinement prompts lack legacy assertions; complete initial requests and historical dirty execution states remain unavailable. Strict historical oracle independence and isolated causal effects are not claimed.",
    "immutability": "Freeze and completed raw attempts are immutable. Resume validates hashes; interrupted attempts are preserved and a new explicit attempt may be created. All failures remain in the population.",
}


def snapshot_iterations(initial: int, pre: int | None, final: int) -> dict[str, int]:
    """Define post-syntax consistently when semantic refinement did not occur."""
    return {"T0": initial, "T1": final if pre is None else pre, "T2": final}


def source_identity(language: str, task: str, context: str, source_hash: str) -> tuple[str, str, str, str]:
    """Identical source bytes only share results within the same task/context."""
    return language, task, context, source_hash


def maven_was_executed(observation: dict[str, Any]) -> bool:
    """A planned command is not an invocation when context preparation failed."""
    return "command" in observation and not observation.get("preparation_error")


def check_reduction_freeze(output: Path) -> dict[str, Any]:
    """Validate archived executor bytes while permitting versioned reporting edits.

    Execution/resume still uses the strict current-code guard in ``check_freeze``.
    Reduction records its own implementation hash and never executes candidates.
    """
    frozen = json.loads((output / "freeze.json").read_text(encoding="utf-8"))
    if fingerprint({k: v for k, v in frozen.items() if k != "freeze_sha256"}) != frozen["freeze_sha256"]:
        raise ValueError("freeze manifest changed")
    for name, expected in frozen["source_inventory"].items():
        path = Path(name)
        archived = output / "implementation" / path.relative_to(REPO_ROOT)
        if sha256(archived) != expected:
            raise ValueError(f"archived executor changed: {archived}")
        if path != Path(__file__).resolve() and sha256(path) != expected:
            raise ValueError(f"imported execution implementation changed: {path}")
    for context in frozen["contexts"]:
        if sha256(Path(context["path"])) != context["context_sha256"]:
            raise ValueError(f"fixed context changed: {context['path']}")
    for job in frozen["jobs"]:
        if sha256(Path(job["source"])) != job["source_sha256"]:
            raise ValueError(f"execution input changed: {job['source']}")
    return frozen


def freeze(output: Path, workers: int, timeout: int) -> None:
    """Freeze inputs and snapshot identities before executing any candidate."""
    output = output.resolve()
    if output.exists():
        raise ValueError("freeze output already exists")
    protected_roots = (TARGET.runs, TARGET.benchmark, TARGET.engines, TARGET.artifacts / "Chosen_for_evaluation", REPO_ROOT / "evaluation/mutants")
    if any(output.is_relative_to(p) for p in protected_roots):
        raise ValueError("output overlaps protected inputs")
    previous = TARGET.artifacts / "legacy-suite-evaluation/campaign-20261008-v1"
    old_freeze = check_freeze(previous)
    protected = json.loads((previous / "protected-inputs.json").read_text(encoding="utf-8"))
    for path, expected in protected.items():
        if sha256(Path(path)) != expected:
            raise ValueError(f"protected input differs from previously qualified campaign: {path}")
    cache = previous / "offline-maven-repository.tar.gz"
    cache_hash = sha256(cache)
    if cache_hash != "908f63b931a6b1a399b00794b7f771b4434f25c5d53689724e0738746d8759a4":
        raise ValueError("frozen offline cache archive changed")
    runs = selected_runs()
    mapping = task_mapping()
    output.mkdir(parents=True)
    (output / "contexts").mkdir()
    contexts = []
    context_paths = {}
    negative_context_paths = {}
    for task in mapping:
        if task.language != "reactions":
            continue
        context, facts = minimal_context(task)
        path = output / "contexts" / (task.task + ".reactions")
        path.write_text(context, encoding="utf-8")
        context_paths[task.task] = str(path)
        contexts.append({**facts, "path": str(path)})
        reference = reference_path(task).read_text(encoding="utf-8")
        composed, _ = compose_reactions(context, reference, reference)
        negative_path = output / "contexts" / (task.task + "-reference-composed.reactions")
        negative_path.write_text(composed, encoding="utf-8")
        negative_context_paths[task.task] = str(negative_path)
        contexts.append({"task": task.task, "path": str(negative_path), "context_sha256": sha256(negative_path),
                         "purpose": "Reference-composed target-absent control; retain original reference routines"})
    jobs = []
    for task in mapping:
        for role in ("reference", "negative") if task.language == "reactions" else ("reference",):
            source = reference_path(task)
            job = {"job_id": f"references--{task.language}--{task.task}--primary--{role}", "phase": "references",
                "role": role, "language": task.language, "task": task.task, "context": "primary",
                "source": str(source), "source_sha256": sha256(source), "reference": str(source)}
            if task.language == "reactions":
                job["context_file"] = negative_context_paths[task.task] if role == "negative" else context_paths[task.task]
            jobs.append(job)
    snapshots = []
    unique = {}
    for run in runs:
        ends = endpoints(run)
        versions = {int(p.parent.name.split("-")[1]): p for p in (run.root / "transformation").glob("iteration-*/metadata.json")}
        if ends is not None and ends.post[0] != run.terminal_result["transformation_iteration"]:
            raise ValueError(f"final adopted iteration mismatch: {run.run_id}")
        indices = {} if ends is None else snapshot_iterations(ends.initial[0], None if ends.pre is None else ends.pre[0], ends.post[0])
        syntax_later = []
        for path in (run.root / "generations/transformation").glob("*/generation.json"):
            generation = json.loads(path.read_text(encoding="utf-8"))
            if ends and ends.semantic_iterations and generation.get("purpose") == "syntax_refinement" and generation["iteration"] > min(ends.semantic_iterations):
                syntax_later.append(generation["iteration"])
        for name in ("T0", "T1", "T2"):
            index = indices.get(name)
            source = None
            if index is not None:
                meta = json.loads(versions[index].read_text(encoding="utf-8"))
                source = REPO_ROOT / meta["transformations"][0]["path"]
                if not source.is_file():
                    source = run.root / meta["transformations"][0]["path"]
            record = {"run_id": run.run_id, "batch_id": run.manifest["batch_id"], "language": run.language,
                "task": run.task, "snapshot": name, "iteration": index, "source": None if source is None else str(source),
                "source_sha256": None if source is None else sha256(source), "source_available": source is not None,
                "later_syntax_iterations": sorted(syntax_later), "job_id": None,
                "unavailable_reason": run.terminal_result["outcome_code"] if source is None else None}
            if source is not None:
                identity = source_identity(run.language, run.task, "primary", record["source_sha256"])
                if identity not in unique:
                    identifier = f"snapshots--{run.language}--{run.task}--primary--{record['source_sha256']}"
                    job = {"job_id": identifier, "phase": "snapshots", "role": "snapshot", "language": run.language,
                        "task": run.task, "context": "primary", "source": str(source), "source_sha256": record["source_sha256"],
                        "reference": str(reference_path(next(t for t in mapping if (t.language, t.task) == (run.language, run.task))))}
                    if run.language == "reactions":
                        job["context_file"] = context_paths[run.task]
                    unique[identity] = job
                    jobs.append(job)
                record["job_id"] = unique[identity]["job_id"]
                protected[str(source)] = record["source_sha256"]
            snapshots.append(record)
    assert len(runs) == 564 and len(snapshots) == 1692
    assert sum(r["source_available"] for r in snapshots if r["snapshot"] == "T0") == 487
    assert len({j["job_id"] for j in jobs}) == len(jobs)
    source_inventory = {}
    for path in [Path(__file__), *sorted((REPO_ROOT / "evaluation/legacy_campaign").glob("*.py")),
                 *sorted((REPO_ROOT / "evaluation/legacy_pilot").glob("*.py"))]:
        source_inventory[str(path)] = sha256(path)
        dest = output / "implementation" / path.relative_to(REPO_ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    environment = {"workers": workers, "timeout_seconds": timeout,
        "java": subprocess.run(["java", "-version"], capture_output=True, text=True, check=True).stderr,
        "maven": subprocess.check_output(["mvn", "-version"], text=True),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True)}
    frozen = {"protocol": PROTOCOL, "environment": environment, "jobs": jobs, "snapshots": snapshots,
        "contexts": contexts, "source_inventory": source_inventory, "maven_jars": old_freeze["maven_jars"],
        "cache": str(cache), "cache_sha256": cache_hash, "prior_qualification_freeze": old_freeze["freeze_sha256"],
        "mapping": mapping_records(mapping), "selected_run_ids": [r.run_id for r in runs]}
    frozen["freeze_sha256"] = fingerprint(frozen)
    write_json(output / "freeze.json", frozen)
    write_json(output / "protected-inputs.json", protected)
    write_csv(output / "snapshot-population.csv", snapshots)
    write_csv(output / "task-to-test-mapping.csv", frozen["mapping"])
    (output / "protocol.md").write_text("# Supplementary T0/T1/T2 legacy evaluation\n\n" + "\n\n".join(f"**{k}**: {v}" for k, v in PROTOCOL.items()) + "\n", encoding="utf-8")
    print(json.dumps({"freeze": frozen["freeze_sha256"], "snapshots": len(snapshots), "saved_runs": 487,
        "unique_candidate_jobs": len(unique), "reference_controls": sum(j["phase"] == "references" for j in jobs)}), flush=True)


def reference_controls(output: Path, frozen: dict[str, Any]) -> list[dict[str, Any]]:
    """Read complete fresh controls and retain unqualified reference reasons."""
    result = []
    for task in task_mapping():
        jobs = [j for j in frozen["jobs"] if j["phase"] == "references" and (j["language"], j["task"]) == (task.language, task.task)]
        facts = {j["role"]: completed(output, j, frozen["freeze_sha256"]) for j in jobs}
        if any(f is None for f in facts.values()):
            raise ValueError(f"reference controls incomplete: {task.language}/{task.task}")
        reference = facts["reference"]
        negative = facts.get("negative")
        valid = qualified(reference["methods"], None if negative is None else negative["methods"])
        outcome = behavioral_outcome(reference["methods"])
        result.append({"language": task.language, "task": task.task, "context": "primary", "qualified": valid,
            "reference_behavioral_outcome": outcome, "reason": None if valid else
            "reference behavioral suite failed" if outcome != "PASS" else "target-reaction dependency control not established",
            "reference_job_id": reference["job"]["job_id"],
            "fixed_inputs_digest": reference.get("fixed_inputs_digest"),
            "runtime_dependencies": reference.get("runtime_dependencies", {}),
            "runtime_properties": runtime_properties(output, reference["job"]["job_id"])})
    return result


def run_phase(output: Path, phase: str) -> None:
    """Execute each unique frozen job once, or validate an existing completion."""
    frozen = check_freeze(output)
    if sha256(Path(frozen["cache"])) != frozen["cache_sha256"]:
        raise ValueError("offline cache archive changed")
    controls = {} if phase == "references" else {(r["language"], r["task"]): r for r in reference_controls(output, frozen)}
    task_index = {(t.language, t.task): t for t in task_mapping()}
    jobs = [j for j in frozen["jobs"] if j["phase"] == phase]
    pending = [j for j in jobs if completed(output, j, frozen["freeze_sha256"]) is None]
    print(json.dumps({"phase": phase, "planned": len(jobs), "pending": len(pending)}), flush=True)
    if pending:
        with tempfile.TemporaryDirectory(prefix="legacy-snapshots-cache-") as directory:
            repository = Path(directory) / "repository"
            repository.mkdir()
            with tarfile.open(frozen["cache"], "r:gz") as archive:
                archive.extractall(Path(directory), filter="data")
            jars = {str(p.relative_to(repository)): sha256(p) for p in repository.rglob("*.jar")}
            if jars != frozen["maven_jars"]:
                raise ValueError("extracted cache differs from frozen JAR population")

            def worker(job: dict[str, Any]) -> dict[str, Any]:
                task = task_index[(job["language"], job["task"])]
                if "context_file" in job:
                    task = with_context(task, Path(job["context_file"]))
                root = output / "raw" / job["job_id"]
                attempt = root / f"attempt-{len(list(root.glob('attempt-*'))) + 1:03d}"
                attempt.mkdir(parents=True)
                write_json(attempt / "started.json", {"job": job, "freeze_sha256": frozen["freeze_sha256"]})
                control = controls.get((job["language"], job["task"]))
                if control is not None and not control["qualified"]:
                    facts = unavailable(task, job, control["reason"])
                    write_csv(attempt / "methods.csv", facts["methods"])
                else:
                    try:
                        facts = execute(task, job, repository, attempt / "trial", frozen["environment"]["timeout_seconds"])
                    except Exception as error:
                        # Preserve host/preparation failure as evidence instead of dropping the job.
                        facts = unavailable(task, job, f"evaluator exception: {type(error).__name__}: {error}")
                        for row in facts["methods"]:
                            row["outcome"] = "INFRASTRUCTURE_ERROR"
                        (attempt / "exception.log").write_text(traceback.format_exc(), encoding="utf-8")
                        write_csv(attempt / "methods.csv", facts["methods"])
                write_json(attempt / "execution.json", facts)
                hashes = {str(p.relative_to(attempt)): sha256(p) for p in attempt.rglob("*") if p.is_file()}
                write_json(attempt / "complete.json", {"job": job, "freeze_sha256": frozen["freeze_sha256"], "raw_hashes": hashes})
                return facts

            with ThreadPoolExecutor(max_workers=frozen["environment"]["workers"]) as executor:
                count = 0
                for future in as_completed([executor.submit(worker, job) for job in pending]):
                    observation = future.result()
                    count += 1
                    if count % 10 == 0 or count == len(pending):
                        print(json.dumps({"phase": phase, "completed_new": count, "total_pending": len(pending),
                            "last_language": observation["job"]["language"], "last_outcome": behavioral_outcome(observation["methods"])}), flush=True)
            final = {str(p.relative_to(repository)): sha256(p) for p in repository.rglob("*.jar")}
            if final != frozen["maven_jars"]:
                raise ValueError("dependency JARs changed during execution")
    observations = [completed(output, j, frozen["freeze_sha256"]) for j in jobs]
    write_json(output / f"{phase}-executions.json", observations)
    write_csv(output / f"{phase}-methods.csv", [r for f in observations for r in f["methods"]])
    if phase == "references":
        rows = reference_controls(output, frozen)
        write_json(output / "reference-qualification.json", rows)
        write_csv(output / "reference-qualification.csv", [{k: v for k, v in r.items() if k not in ("runtime_dependencies", "runtime_properties")} for r in rows])
        print(json.dumps({"reference_qualification": {lang: [sum(r["qualified"] for r in rows if r["language"] == lang), sum(r["language"] == lang for r in rows)] for lang in ("atl", "etl", "qvto", "reactions")},
            "blockers": [{"language": r["language"], "task": r["task"], "reason": r["reason"]} for r in rows if not r["qualified"]]}), flush=True)


def reduce(output: Path) -> None:
    """Validate fixed inputs and produce all 1692 snapshot slots from raw evidence."""
    frozen = check_reduction_freeze(output)
    controls = {(r["language"], r["task"]): r for r in reference_controls(output, frozen)}
    outcomes = {}
    corrections = []
    mismatches = []
    durations = []
    methods = []
    issues = []
    for job in frozen["jobs"]:
        observation = completed(output, job, frozen["freeze_sha256"])
        if observation is None:
            raise ValueError(f"unfinished job: {job['job_id']}")
        recovered, adjustment = recover_listener_failures(output, observation)
        corrections.extend(adjustment)
        durations.append({"job_id": job["job_id"], "phase": job["phase"], "language": job["language"],
            "maven_executed": maven_was_executed(observation), "duration_seconds": observation["duration_seconds"],
            "timed_out": observation.get("timed_out", False)})
        if observation.get("preparation_error"):
            issues.append({"job_id": job["job_id"], "phase": job["phase"], "language": job["language"],
                "task": job["task"], "maven_executed": False, "kind": "CONTEXT_PREPARATION_FAILURE",
                "detail": observation["preparation_error"], "outcome": behavioral_outcome(recovered["methods"])})
        if job["phase"] == "references":
            continue
        control = controls[(job["language"], job["task"])]
        runtime = runtime_properties(output, job["job_id"])
        fixed_ok = observation.get("fixed_inputs_digest") == control["fixed_inputs_digest"] if control["qualified"] else None
        dependencies_ok = observation.get("runtime_dependencies") == control["runtime_dependencies"] if observation.get("runtime_dependencies") else None
        runtime_ok = runtime == control["runtime_properties"] if runtime else None
        if fixed_ok is False or dependencies_ok is False or runtime_ok is False:
            mismatches.append({"job_id": job["job_id"], "fixed_inputs_identical": fixed_ok,
                               "dependencies_identical": dependencies_ok, "runtime_identical": runtime_ok})
        outcomes[job["job_id"]] = {"legacy_outcome": behavioral_outcome(recovered["methods"]),
            "reference_qualified": control["qualified"], "qualification_reason": control["reason"],
            "fixed_inputs_identical": fixed_ok, "runtime_dependencies_identical": dependencies_ok,
            "runtime_properties_identical": runtime_ok, "runtime_properties": runtime,
            "behavioral_methods": sum(r["strength"] == "behavioral" for r in recovered["methods"]),
            "behavioral_methods_pass": sum(r["strength"] == "behavioral" and r["outcome"] == "PASS" for r in recovered["methods"])}
        methods.extend(recovered["methods"])
    if mismatches:
        write_json(output / "execution-comparability-errors.json", mismatches)
        raise ValueError("candidate/reference environment mismatch; see preserved evidence")
    rows = []
    for snapshot in frozen["snapshots"]:
        control = controls[(snapshot["language"], snapshot["task"])]
        fact = outcomes.get(snapshot["job_id"])
        rows.append({**snapshot, **(fact or {"legacy_outcome": "UNAVAILABLE", "reference_qualified": control["qualified"],
            "qualification_reason": snapshot["unavailable_reason"], "fixed_inputs_identical": None,
            "runtime_dependencies_identical": None, "runtime_properties_identical": None,
            "runtime_properties": {}, "behavioral_methods": None, "behavioral_methods_pass": None})})
    assert len(rows) == 1692
    protected = json.loads((output / "protected-inputs.json").read_text(encoding="utf-8"))
    changed = [p for p, h in protected.items() if sha256(Path(p)) != h]
    write_json(output / "snapshot-outcomes.json", rows)
    write_csv(output / "snapshot-outcomes.csv", [{k: v for k, v in r.items() if k != "runtime_properties"} for r in rows])
    method_fields = list(dict.fromkeys(k for row in methods for k in row))
    write_csv(output / "derived-method-outcomes.csv", [{k: row.get(k) for k in method_fields} for row in methods])
    write_csv(output / "classification-corrections.csv", corrections)
    write_csv(output / "execution-durations.csv", durations)
    write_csv(output / "execution-issues.csv", issues)
    validation = {"freeze_sha256": frozen["freeze_sha256"], "jobs": len(frozen["jobs"]),
        "maven_executions": sum(r["maven_executed"] for r in durations),
        "context_preparation_failures": len(issues),
        "frozen_execution_implementation_sha256": frozen["source_inventory"][str(Path(__file__).resolve())],
        "reporting_implementation_sha256": sha256(Path(__file__)),
        "maven_duration_seconds": sum(r["duration_seconds"] for r in durations),
        "timeouts": sum(r["timed_out"] for r in durations), "snapshots": len(rows),
        "protected_files": len(protected), "protected_mismatches": changed,
        "comparability_mismatches": mismatches, "classification_corrections": len(corrections),
        "snapshot_outcomes": {name: dict(Counter(r["legacy_outcome"] for r in rows if r["snapshot"] == name)) for name in ("T0", "T1", "T2")}}
    write_json(output / "integrity.json", validation)
    shutil.copy2(Path(__file__), output / "reporting-implementation.py")
    print(json.dumps(validation, indent=2), flush=True)
    if changed:
        raise ValueError("protected inputs changed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("freeze", "references", "snapshots", "reduce"), required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if args.workers < 1 or args.timeout < 1:
        parser.error("workers and timeout must be positive")
    if args.phase == "freeze":
        freeze(args.output, args.workers, args.timeout)
    elif args.phase == "reduce":
        reduce(args.output)
    else:
        run_phase(args.output, args.phase)


if __name__ == "__main__":
    main()
