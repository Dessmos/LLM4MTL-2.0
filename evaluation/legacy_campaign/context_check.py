"""Additional frozen Reactions dependency controls, separate from campaign v1.

Reference qualification revealed two configurations requiring full context.
Before mutant execution, test target dependence in both contexts, retaining the
reference-composed routines. Primary v1 failures remain visible and unchanged.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluation.legacy_campaign.execution import execute
from evaluation.legacy_campaign.protocol import reference_path, with_context, qualified
from evaluation.legacy_campaign.run import check_freeze, completed, fingerprint, read_json
from evaluation.legacy_pilot.assessment import sha256, task_mapping
from evaluation.legacy_pilot.run_pilot import compose_reactions, write_csv, write_json
from llm4mtl.paths import REPO_ROOT


def freeze_controls(campaign: Path, output: Path) -> None:
    frozen = check_freeze(campaign)
    if output.exists():
        raise ValueError("additional control freeze must be new")
    output.mkdir(parents=True)
    jobs = []
    tasks = [task for task in task_mapping() if task.language == "reactions"]
    for task in tasks:
        for context in ("primary", "full"):
            base = campaign / "contexts" / (task.task + ".reactions") if context == "primary" else task.context_file
            prepared, facts = compose_reactions(base.read_text(encoding="utf-8"),
                reference_path(task).read_text(encoding="utf-8"), reference_path(task).read_text(encoding="utf-8"))
            path = output / "contexts" / (task.task + "--" + context + ".reactions")
            path.parent.mkdir(exist_ok=True)
            path.write_text(prepared, encoding="utf-8")
            jobs.append({"job_id": f"dependency--{task.task}--{context}", "phase": "references", "role": "negative",
                "language": "reactions", "task": task.task, "context": context,
                "source": str(reference_path(task)), "source_sha256": sha256(reference_path(task)),
                "reference": str(reference_path(task)), "fixed_context": str(path), "context_sha256": sha256(path),
                "composition": facts})
    alternate = ("FamiliesToPersons_DeletedFamily", "NetworkToGraph_ComponentRenamed")
    for mutant in frozen["mutants"]:
        if mutant["task"] in alternate:
            task = next(task for task in tasks if task.task == mutant["task"])
            jobs.append({"job_id": f"full-mutant--{task.task}--{mutant['mutant']}", "phase": "mutants", "role": "mutant",
                "language": "reactions", "task": task.task, "context": "full", "operator": mutant["mutant"],
                "source": mutant["source"], "source_sha256": mutant["mutant_sha256"], "reference": str(reference_path(task)),
                "fixed_context": str(task.context_file), "context_sha256": sha256(task.context_file)})
    payload = {"schema_version": "supplementary-dependency-1.0", "parent": str(campaign),
        "parent_freeze": frozen["freeze_sha256"], "jobs": jobs,
        "definition": "Target-absent controls remove only the target reaction from the reference-composed context, retaining reference routines. All original v1 primary results remain. Full-context mutant observations are secondary, only for the two primary-reference-failing tasks whose full reference passed, and only if these full controls establish target dependence. No changes to tests, references or mutants; alternate contexts selected before any mutant result.",
        "source_hashes": {str(path): sha256(path) for path in (Path(__file__), REPO_ROOT / "evaluation/legacy_campaign/execution.py")}}
    payload["freeze_sha256"] = fingerprint(payload)
    write_json(output / "freeze.json", payload)
    shutil.copy2(Path(__file__), output / "context_check.py")
    print(json.dumps({"control_freeze": payload["freeze_sha256"], "dependency_jobs": 24, "secondary_mutant_slots": 11}), flush=True)


def run(campaign: Path, output: Path, phase: str) -> None:
    parent = check_freeze(campaign)
    frozen = read_json(output / "freeze.json")
    if frozen["parent_freeze"] != parent["freeze_sha256"] or fingerprint({key: value for key, value in frozen.items() if key != "freeze_sha256"}) != frozen["freeze_sha256"]:
        raise ValueError("additional control freeze changed")
    for path, digest in frozen["source_hashes"].items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"additional control implementation changed: {path}")
    task_index = {task.task: task for task in task_mapping() if task.language == "reactions"}
    jobs = [job for job in frozen["jobs"] if job["phase"] == phase]
    with tempfile.TemporaryDirectory(prefix="legacy-context-cache-") as temporary:
        repository = Path(temporary) / "repository"
        shutil.copytree(Path.home() / ".m2/repository", repository)
        jars = {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")}
        if jars != parent["maven_jars"]:
            raise ValueError("additional control dependency cache differs")

        def worker(job: dict[str, Any]) -> dict[str, Any]:
            existing = completed(output, job, frozen["freeze_sha256"])
            if existing:
                return existing
            if sha256(Path(job["fixed_context"])) != job["context_sha256"] or sha256(Path(job["source"])) != job["source_sha256"]:
                raise ValueError("additional control execution input changed")
            task = with_context(task_index[job["task"]], Path(job["fixed_context"]))
            root = output / "raw" / job["job_id"]
            attempt = root / f"attempt-{len(list(root.glob('attempt-*'))) + 1:03d}"
            attempt.mkdir(parents=True)
            reason = ""
            if phase == "mutants":
                control_job = next(item for item in frozen["jobs"] if item["phase"] == "references" and item["task"] == task.task and item["context"] == "full")
                control = completed(output, control_job, frozen["freeze_sha256"])
                ref_job = next(item for item in parent["jobs"] if item["phase"] == "references" and item["task"] == task.task and item["context"] == "full" and item["role"] == "reference")
                reference = completed(campaign, ref_job, parent["freeze_sha256"])
                if control is None or not qualified(reference["methods"], control["methods"]):
                    reason = "full-context behavioral test does not depend on target reaction, or control unqualified"
            if reason:
                from evaluation.legacy_campaign.run import unavailable
                facts = unavailable(task, job, reason)
            else:
                facts = execute(task, job, repository, attempt / "trial", parent["environment"]["timeout_seconds"])
            write_json(attempt / "execution.json", facts)
            write_csv(attempt / "methods.csv", facts["methods"])
            hashes = {str(path.relative_to(attempt)): sha256(path) for path in attempt.rglob("*") if path.is_file()}
            write_json(attempt / "complete.json", {"job": job, "freeze_sha256": frozen["freeze_sha256"], "raw_hashes": hashes})
            print(json.dumps({"additional_job": job["job_id"], "outcomes": [row["outcome"] for row in facts["methods"]]}), flush=True)
            return facts

        with ThreadPoolExecutor(max_workers=2) as executor:
            facts = [future.result() for future in as_completed([executor.submit(worker, job) for job in jobs])]
        if {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")} != jars:
            raise ValueError("additional control dependency cache changed")
    write_json(output / (phase + "-executions.json"), facts)
    write_csv(output / (phase + "-methods.csv"), [row for item in facts for row in item["methods"]])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=("freeze", "references", "mutants"), required=True)
    args = parser.parse_args()
    if args.phase == "freeze":
        freeze_controls(args.campaign.resolve(), args.output.resolve())
    else:
        run(args.campaign.resolve(), args.output.resolve(), args.phase)


if __name__ == "__main__":
    main()
