"""Resumable supplementary campaign; original runs and canonical CSVs are read-only.

PYTHONPATH=pipeline/src:. .venv/bin/python -B -m evaluation.legacy_campaign.run
    --output artifacts/legacy-suite-evaluation/campaign-20261008-v1 --phase freeze
    --phase references / pairs / mutants / integrity use the same output.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluation.legacy_campaign.execution import execute
from evaluation.legacy_campaign.protocol import (
    PROTOCOL, behavioral_outcome, endpoint_record, minimal_context, qualified,
    reference_path, with_context,
)
from evaluation.legacy_pilot.assessment import mapping_records, selected_runs, sha256, task_mapping
from evaluation.legacy_pilot.run_pilot import tree_hashes, write_csv, write_json
from llm4mtl.paths import REPO_ROOT, TARGET


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fingerprint(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def generated_rows(runs: tuple[Any, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read only the original matrices adjacent to the twelve selection CSVs."""
    selected = {run.run_id: run for run in runs}
    rows, excluded = [], []
    seen = set()
    for selection in sorted((TARGET.artifacts / "Chosen_for_evaluation").rglob("batch-runs.csv")):
        for matrix in sorted(selection.parent.glob("mutants*.csv")):
            with matrix.open(encoding="utf-8", newline="") as stream:
                for line, item in enumerate(csv.DictReader(stream), 2):
                    row = dict(item, artifact=str(matrix), artifact_sha256=sha256(matrix), csv_line=line)
                    if item["run_id"] not in selected:
                        excluded.append(row)
                        continue
                    run = selected[item["run_id"]]
                    if (item["language"].lower(), item["task"]) != (run.language, run.task):
                        raise ValueError(f"generated mutation task mismatch: {matrix}:{line}")
                    if run.run_id in seen:
                        raise ValueError(f"duplicate generated run population: {run.run_id}")
                    seen.add(run.run_id)
                    rows.append(row)
    if len(rows) != 564 or len(excluded) != 4:
        raise ValueError(f"mutation population mismatch: {len(rows)} selected, {len(excluded)} excluded")
    return rows, excluded


def freeze(output: Path, workers: int, timeout: int) -> None:
    if output.exists():
        raise ValueError("freeze output already exists; resume a phase instead")
    forbidden = (TARGET.runs, TARGET.benchmark, TARGET.engines,
        TARGET.artifacts / "Chosen_for_evaluation", REPO_ROOT / "evaluation/mutants")
    if any(output.is_relative_to(path) for path in forbidden):
        raise ValueError("output overlaps protected input")
    runs = selected_runs()
    mapping = task_mapping()
    pairs = [row for run in runs if (row := endpoint_record(run)) is not None]
    catalog_path = REPO_ROOT / "evaluation/mutants/manifest.json"
    catalog = read_json(catalog_path)
    mutants = []
    for entry in catalog["mutants"]:
        if entry["status"] != "PRESENT":
            continue
        path = REPO_ROOT / entry["file"]
        if sha256(path) != entry["mutant_sha256"]:
            raise ValueError(f"catalogue hash mismatch: {path}")
        mutants.append(dict(entry, language=entry["language"].lower(), source=str(path)))
    if len(pairs) != 120 or len(mutants) != 289 or sum(row["syntax_sensitivity_exclusion"] for row in pairs) != 3:
        raise ValueError("supplementary population differs from authorized 120 / 289 / 3")
    matrices, excluded = generated_rows(runs)
    output.mkdir(parents=True)
    contexts = output / "contexts"
    contexts.mkdir()
    context_records = []
    for task in mapping:
        if task.language == "reactions":
            text, facts = minimal_context(task)
            path = contexts / (task.task + ".reactions")
            path.write_text(text, encoding="utf-8")
            context_records.append(dict(facts, path=str(path)))
    jobs = []

    def job(task: Any, phase: str, role: str, source: Path, context: str = "primary", **extra: Any) -> None:
        identity = f"{phase}--{task.language}--{extra.get('run_id', task.task)}--{context}--{extra.get('operator', role)}"
        jobs.append({"job_id": identity, "phase": phase, "role": role, "language": task.language,
            "task": task.task, "context": context, "source": str(source), "source_sha256": sha256(source),
            "reference": str(reference_path(task)), **extra})

    by_task = {(task.language, task.task): task for task in mapping}
    for task in mapping:
        job(task, "references", "reference", reference_path(task))
        if task.language == "reactions":
            job(task, "references", "reference", reference_path(task), "full")
            job(task, "references", "negative", reference_path(task))
    for pair in pairs:
        task = by_task[(pair["language"], pair["task"])]
        for role in ("Tpre", "Tpost"):
            job(task, "pairs", role, Path(pair[role]), run_id=pair["run_id"],
                syntax_sensitivity_exclusion=pair["syntax_sensitivity_exclusion"])
            if task.language == "reactions":
                job(task, "pairs", role, Path(pair[role]), "full", run_id=pair["run_id"],
                    syntax_sensitivity_exclusion=pair["syntax_sensitivity_exclusion"])
    for mutant in mutants:
        task = by_task[(mutant["language"], mutant["task"])]
        job(task, "mutants", "mutant", Path(mutant["source"]), operator=mutant["mutant"], category=mutant["category"])
    if len({item["job_id"] for item in jobs}) != len(jobs):
        raise ValueError("duplicate job identities")
    protected = {}
    for root in (TARGET.benchmark, TARGET.engines, TARGET.artifacts / "Chosen_for_evaluation", REPO_ROOT / "evaluation/mutants"):
        protected.update({str(root / name): digest for name, digest in tree_hashes(root).items()})
    for run in runs:
        for relative in ("manifest.json", "result.json", "events.jsonl"):
            path = run.root / relative
            if path.exists():
                protected[str(path)] = sha256(path)
        for subtree in ("transformation", "generations/transformation"):
            for path in (run.root / subtree).rglob("*"):
                if path.is_file():
                    protected[str(path)] = sha256(path)
    for pair in pairs:
        for path in pair["semantic_requests"] + [item["path"] for item in pair["final_execution_evidence"]]:
            protected[path] = sha256(Path(path))
    source_inventory = {}
    snapshot = output / "implementation"
    for module in (REPO_ROOT / "evaluation/legacy_campaign", REPO_ROOT / "evaluation/legacy_pilot"):
        for source in sorted(module.glob("*.py")):
            relative = source.relative_to(REPO_ROOT)
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            source_inventory[str(source)] = sha256(source)
    cache = Path.home() / ".m2/repository"
    jars = {str(path.relative_to(cache)): sha256(path) for path in sorted(cache.rglob("*.jar"))}
    versions = {"git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "--porcelain"], text=True),
        "java": subprocess.run(["java", "-version"], capture_output=True, text=True).stderr,
        "maven": subprocess.check_output(["mvn", "-version"], text=True), "workers": workers, "timeout_seconds": timeout}
    manifest = {"protocol": PROTOCOL, "environment": versions, "selected_run_ids": [run.run_id for run in runs],
        "pairs": pairs, "mutants": mutants, "jobs": jobs, "contexts": context_records,
        "mapping": mapping_records(mapping), "source_inventory": source_inventory, "maven_jars": jars,
        "generated_matrix_rows": matrices, "excluded_generated_attempts": excluded,
        "historical_mutant_hash_limit": "Original matrix CSVs carry identities, not per-execution mutant hashes. Current catalogue files match manifest hashes; historical byte-level correspondence cannot be independently certified from these CSVs alone."}
    manifest["freeze_sha256"] = fingerprint(manifest)
    write_json(output / "freeze.json", manifest)
    write_json(output / "protected-inputs.json", protected)
    write_csv(output / "task-to-test-mapping.csv", manifest["mapping"])
    write_json(output / "paired-population.json", pairs)
    write_json(output / "mutant-population.json", mutants)
    (output / "protocol.md").write_text("# Supplementary legacy evaluation protocol\n\n" + "\n\n".join(
        f"**{key}**: {value}" for key, value in PROTOCOL.items()) + "\n", encoding="utf-8")
    print(json.dumps({"freeze": manifest["freeze_sha256"], "jobs": len(jobs), "protected_files": len(protected),
        "pairs": len(pairs), "mutants": len(mutants), "phases": dict(Counter(item["phase"] for item in jobs))}), flush=True)


def check_freeze(output: Path) -> dict[str, Any]:
    frozen = read_json(output / "freeze.json")
    expected = frozen["freeze_sha256"]
    if fingerprint({key: value for key, value in frozen.items() if key != "freeze_sha256"}) != expected:
        raise ValueError("freeze manifest changed")
    for path, digest in frozen["source_inventory"].items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"execution implementation changed after freeze: {path}")
    for context in frozen["contexts"]:
        if sha256(Path(context["path"])) != context["context_sha256"]:
            raise ValueError(f"fixed context changed: {context['path']}")
    for job in frozen["jobs"]:
        if sha256(Path(job["source"])) != job["source_sha256"]:
            raise ValueError(f"execution input changed: {job['source']}")
    return frozen


def completed(output: Path, job: dict[str, Any], freeze_hash: str) -> dict[str, Any] | None:
    root = output / "raw" / job["job_id"]
    for attempt in sorted(root.glob("attempt-*")):
        marker = attempt / "complete.json"
        if marker.exists():
            fact = read_json(marker)
            if fact["freeze_sha256"] != freeze_hash or fact["job"] != job:
                raise ValueError(f"resume fingerprint mismatch: {marker}")
            for relative, digest in fact["raw_hashes"].items():
                if sha256(attempt / relative) != digest:
                    raise ValueError(f"raw evidence changed: {attempt / relative}")
            return read_json(attempt / "execution.json")
    return None


def unavailable(task: Any, job: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"job": job, "unavailable_reason": reason, "duration_seconds": 0,
        "fixed_inputs_digest": None, "runtime_dependencies": {}, "methods": [
        {"job_id": job["job_id"], "run_id": job.get("run_id", ""), "language": task.language,
         "task": task.task, "role": job["role"], "context": job["context"], "operator": job.get("operator", ""),
         "class": task.class_name, "method": case.method, "strength": case.strength,
         "observed": False, "outcome": "UNAVAILABLE", "detail": reason} for case in task.cases]}


def qualification(output: Path, frozen: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for task in task_mapping():
        for context in ("primary", "full") if task.language == "reactions" else ("primary",):
            jobs = [job for job in frozen["jobs"] if job["phase"] == "references" and job["language"] == task.language
                and job["task"] == task.task and job["context"] == context]
            ref_job = next(job for job in jobs if job["role"] == "reference")
            reference = completed(output, ref_job, frozen["freeze_sha256"])
            if reference is None:
                raise ValueError(f"missing reference qualification job: {ref_job['job_id']}")
            negative_job = next((job for job in jobs if job["role"] == "negative"), None)
            negative = None if negative_job is None else completed(output, negative_job, frozen["freeze_sha256"])
            if negative_job is not None and negative is None:
                raise ValueError(f"missing dependency control: {negative_job['job_id']}")
            valid = qualified(reference["methods"], None if negative is None else negative["methods"])
            # Full-context qualification is integration-only; primary reaction dependency
            # control is recorded separately, and gates full paired execution too.
            rows.append({"language": task.language, "task": task.task, "context": context,
                "qualified": valid, "reference_behavioral_outcome": behavioral_outcome(reference["methods"]),
                "methods": reference["methods"], "negative_methods": [] if negative is None else negative["methods"],
                "reason": "" if valid else "reference behavioral suite failed" if behavioral_outcome(reference["methods"]) != "PASS"
                    else "target-reaction dependency control not established"})
    return rows


def run_phase(output: Path, phase: str) -> None:
    frozen = check_freeze(output)
    task_index = {(task.language, task.task): task for task in task_mapping()}
    qualified_index = {}
    if phase != "references":
        for row in qualification(output, frozen):
            qualified_index[(row["language"], row["task"], row["context"])] = row
    jobs = [job for job in frozen["jobs"] if job["phase"] == phase]
    remaining = [job for job in jobs if completed(output, job, frozen["freeze_sha256"]) is None]
    print(json.dumps({"phase": phase, "planned": len(jobs), "remaining": len(remaining)}), flush=True)
    with tempfile.TemporaryDirectory(prefix="legacy-campaign-cache-") as temporary:
        repository = Path(temporary) / "repository"
        shutil.copytree(Path.home() / ".m2/repository", repository)
        current_jars = {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")}
        if current_jars != frozen["maven_jars"]:
            raise ValueError("local Maven JAR population changed since freeze")

        def worker(job: dict[str, Any]) -> dict[str, Any]:
            task = task_index[(job["language"], job["task"])]
            if task.language == "reactions" and job["context"] == "primary":
                task = with_context(task, output / "contexts" / (task.task + ".reactions"))
            root = output / "raw" / job["job_id"]
            attempts = sorted(root.glob("attempt-*"))
            attempt = root / f"attempt-{len(attempts) + 1:03d}"
            attempt.mkdir(parents=True)
            write_json(attempt / "started.json", {"job": job, "freeze_sha256": frozen["freeze_sha256"]})
            reason = ""
            if phase != "references":
                control = qualified_index[(task.language, task.task, job["context"])]
                if not control["qualified"]:
                    reason = control["reason"]
                if task.language == "reactions" and not qualified_index[(task.language, task.task, "primary")]["qualified"]:
                    reason = "primary Reactions reference/dependency control unqualified"
            if reason:
                facts = unavailable(task, job, reason)
                write_json(attempt / "execution.json", facts)
                write_csv(attempt / "methods.csv", facts["methods"])
            else:
                try:
                    facts = execute(task, job, repository, attempt / "trial", frozen["environment"]["timeout_seconds"])
                    write_json(attempt / "execution.json", facts)
                except Exception as error:
                    # A host/preparation failure must keep the job visible, not drop it.
                    facts = unavailable(task, job, f"evaluator exception: {type(error).__name__}: {error}")
                    for row in facts["methods"]:
                        row["outcome"] = "INFRASTRUCTURE_ERROR"
                    (attempt / "exception.log").write_text(traceback.format_exc(), encoding="utf-8")
                    write_json(attempt / "execution.json", facts)
                    write_csv(attempt / "methods.csv", facts["methods"])
            hashes = {str(path.relative_to(attempt)): sha256(path) for path in attempt.rglob("*") if path.is_file()}
            write_json(attempt / "complete.json", {"job": job, "freeze_sha256": frozen["freeze_sha256"], "raw_hashes": hashes})
            print(json.dumps({"job": job["job_id"], "seconds": round(facts["duration_seconds"], 2),
                "outcomes": [row["outcome"] for row in facts["methods"]]}), flush=True)
            return facts

        with ThreadPoolExecutor(max_workers=frozen["environment"]["workers"]) as executor:
            for future in as_completed([executor.submit(worker, job) for job in remaining]):
                future.result()
        final_jars = {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")}
        if final_jars != frozen["maven_jars"]:
            raise ValueError("Maven dependency JARs changed during execution")
    facts = [completed(output, job, frozen["freeze_sha256"]) for job in jobs]
    write_json(output / (phase + "-executions.json"), facts)
    write_csv(output / (phase + "-methods.csv"), [row for item in facts for row in item["methods"]])
    if phase == "references":
        controls = qualification(output, frozen)
        write_json(output / "reference-qualification.json", controls)
        write_csv(output / "reference-qualification.csv", [{key: value for key, value in row.items()
            if key not in ("methods", "negative_methods")} for row in controls])
        primary = [row for row in controls if row["context"] == "primary"]
        lines = ["# Reference qualification\n", f"Primary task contexts qualified: {sum(row['qualified'] for row in primary)}/47.\n"]
        for language in ("atl", "etl", "qvto", "reactions"):
            language_rows = [row for row in primary if row["language"] == language]
            lines.append(f"- {language}: {sum(row['qualified'] for row in language_rows)}/{len(language_rows)} qualified.")
        lines += ["\n## Blockers\n"] + [f"- {row['language']} / {row['task']} / {row['context']}: {row['reason']} ({row['reference_behavioral_outcome']})." for row in controls if not row["qualified"]]
        lines += ["\nAssertions, fixtures and references were not repaired. Reactions task-specific context qualification does not establish full application integration. Raw method results, compiler failures and target-absent controls are retained in references-methods.csv and raw/.\n"]
        (output / "reference-qualification.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines), flush=True)


def integrity(output: Path) -> None:
    frozen = check_freeze(output)
    protected = read_json(output / "protected-inputs.json")
    mismatches = [path for path, digest in protected.items() if not Path(path).is_file() or sha256(Path(path)) != digest]
    jobs_complete = 0
    for job in frozen["jobs"]:
        if completed(output, job, frozen["freeze_sha256"]) is not None:
            jobs_complete += 1
    result = {"protected_files": len(protected), "protected_mismatches": mismatches,
        "jobs_complete": jobs_complete, "jobs_frozen": len(frozen["jobs"]), "freeze_sha256": frozen["freeze_sha256"]}
    write_json(output / "integrity.json", result)
    print(json.dumps(result), flush=True)
    if mismatches or jobs_complete != len(frozen["jobs"]):
        raise ValueError("supplementary integrity check failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("freeze", "references", "pairs", "mutants", "integrity"), required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if arguments.phase == "freeze":
        if not 1 <= arguments.workers <= 4 or arguments.timeout <= 0:
            parser.error("workers must be 1..4 and timeout positive")
        freeze(output, arguments.workers, arguments.timeout)
    elif arguments.phase == "integrity":
        integrity(output)
    else:
        run_phase(output, arguments.phase)


if __name__ == "__main__":
    main()
