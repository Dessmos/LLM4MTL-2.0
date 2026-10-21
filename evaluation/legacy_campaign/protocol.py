from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from evaluation.legacy_pilot.assessment import LegacyTask, endpoints, sha256
from evaluation.legacy_pilot.run_pilot import source_blocks
from llm4mtl.paths import TARGET


# Chosen from the original Java stimuli and their setup, before qualification.
# Shared routine declarations are retained once, as exact legacy context blocks.
PREREQUISITES = {
    "FamiliesToPersons_InsertedFamilyRegister": (),
    "FamiliesToPersons_CreatedFather": ("FamiliesToPersons_InsertedFamilyRegister",),
    "FamiliesToPersons_InsertedDaughter": ("FamiliesToPersons_InsertedFamilyRegister",),
    "FamiliesToPersons_DeletedMember": ("FamiliesToPersons_InsertedFamilyRegister", "FamiliesToPersons_CreatedFather"),
    "FamiliesToPersons_DeletedFamily": ("FamiliesToPersons_InsertedFamilyRegister", "FamiliesToPersons_CreatedFather", "FamiliesToPersons_InsertedDaughter"),
    "NetworkToGraph_CreateAndRegisterRoot": (),
    "NetworkToGraph_ComponentInsertedIntoSystem": ("NetworkToGraph_CreateAndRegisterRoot",),
    "NetworkToGraph_ComponentRenamed": ("NetworkToGraph_CreateAndRegisterRoot", "NetworkToGraph_ComponentInsertedIntoSystem"),
    "NetworkToGraph_ComponentDeleted": ("NetworkToGraph_CreateAndRegisterRoot", "NetworkToGraph_ComponentInsertedIntoSystem"),
    "AmaltheaToAscet_ComponentContainerInsertedAsRoot": (),
    "AmaltheaToAscet_TaskCreated": ("AmaltheaToAscet_ComponentContainerInsertedAsRoot",),
    "AmaltheaToAscet_TaskDeleted": ("AmaltheaToAscet_ComponentContainerInsertedAsRoot", "AmaltheaToAscet_TaskCreated"),
}

PROTOCOL = {
    "schema_version": "supplementary-legacy-1.0",
    "scope": "47 reference controls; 120 Tpre/Tpost pairs; 289 unique PRESENT mutants; no T0 campaign",
    "independence": "Inspected refinement prompts contained no original assertions. Complete initial requests and historical dirty execution states were unavailable; strict historical oracle independence is not established.",
    "endpoint": "Tpre is the input to the first semantic transformation refinement. Tpost is the final saved iteration, checked against terminal result.json and generation hash; archived matching execution hashes distinguish adopted from evaluated.",
    "context": "Reactions primary evidence uses fixed task-specific original legacy blocks selected from test setup/stimuli. Full original context reference controls and paired sensitivity are separate integration evidence. Candidate-absent controls remove only the target reaction, retaining routines.",
    "qualification": "All mapped behavioral methods must be observed PASS on the reference. For Reactions at least one behavioral method must be observed non-PASS after removing the target reaction, with no compilation/infrastructure failure. Reference failures are not repaired. Smoke and source-only weak methods are reported but do not gate behavioral qualification or metrics.",
    "paired_population": "All 120 runs retained. Unqualified contexts/endpoints produce UNAVAILABLE method slots. Qualified-population rates and all-selected rates reported separately.",
    "suite_success": "All mapped behavioral methods observed PASS; technical and UNAVAILABLE slots never count as PASS.",
    "method_rate": "Behavioral PASS / all mapped behavioral method slots in the stated population, including technical and UNAVAILABLE slots.",
    "repair": "Full behavioral suite non-PASS at Tpre and PASS at Tpost / qualified pairs whose Tpre suite is non-PASS. Technical baseline failures remain explicitly separated from assertion-only repairs.",
    "regression": "Behavioral PASS at Tpre becoming non-PASS at Tpost / behavioral methods PASS at Tpre. Assertion regressions and technical losses separated.",
    "sensitivity": "Exclude exactly three runs with syntax refinement after the first semantic refinement; separately report full-context Reactions pairs.",
    "manual_mutation": "Qualified behavioral suite only: KILLED iff all methods are observed and have PASS/ASSERTION_FAILURE outcomes, and at least one reference-passing behavioral method has ASSERTION_FAILURE. Any behavioral compilation/runtime/infrastructure error takes precedence over kills. SURVIVED iff every behavioral method PASS. Weak/smoke outcomes reported independently. UNAVAILABLE for unqualified references. This catalogue result is not MS_Q.",
    "generated_match": "Filter frozen mutation CSVs by the exact 564 selected run IDs. Unique identity=(language,task,operator), source hash verified against catalogue. Comparable manual KILLED/SURVIVED and generated reference PASS plus KILLED/SURVIVED. Unique comparison uses ANY valid generated kill and describes cumulative detection opportunities, not equal test budgets. Run-mutant comparisons retained separately, with repeats clustered by identity and no independence/significance claim.",
    "failure_policy": "No outcome-seeking retries. Each job's raw attempt directory is immutable after completion. Interrupted attempts remain archived and a new attempt is explicit on resume. Unavailable jobs have a persisted reason; no fabricated observations.",
    "environment": "Offline Maven; isolated engine copies and copied local cache; JDK17; TZ=UTC; fixed English locale, UTF-8 and JVM heap. Dependencies, templates, fixtures, tests and context hashes frozen before execution.",
}


def reference_path(task: LegacyTask) -> Path:
    extension = {"atl": ".atl", "etl": ".etl", "qvto": ".qvto", "reactions": ".reactions"}[task.language]
    return TARGET.benchmark / "tasks" / task.language / "references" / (task.task + extension)


def minimal_context(task: LegacyTask) -> tuple[str, dict[str, Any]]:
    """Select exact original blocks from a predeclared test-stimulus closure."""
    original = task.context_file.read_text(encoding="utf-8")
    names = (task.task, *PREREQUISITES[task.task])
    references = [TARGET.benchmark / "tasks/reactions/references" / (name + ".reactions") for name in names]
    allowed = {(block.kind, block.name) for path in references for block in source_blocks(path.read_text(encoding="utf-8"))}
    blocks = source_blocks(original)
    present = {(block.kind, block.name) for block in blocks}
    if not allowed.issubset(present):
        raise ValueError(f"missing original prerequisite blocks: {task.task}: {allowed - present}")
    result = original
    for block in reversed(blocks):
        if (block.kind, block.name) not in allowed:
            result = result[:block.start] + result[block.end:]
    return result, {"task": task.task, "original_context": str(task.context_file),
        "original_sha256": sha256(task.context_file), "prerequisite_tasks": list(PREREQUISITES[task.task]),
        "retained_declarations": sorted(f"{kind}:{name}" for kind, name in allowed),
        "context_sha256": hashlib.sha256(result.encode("utf-8")).hexdigest(),
        "evidence_basis": str(task.java_file), "integration_scope": "task-specific fixed legacy context"}


def endpoint_record(run: Any) -> dict[str, Any] | None:
    versions = endpoints(run)
    if versions is None or not versions.semantic_iterations:
        return None
    final = versions.post
    if run.terminal_result["transformation_iteration"] != final[0]:
        raise ValueError(f"terminal / archived final mismatch: {run.run_id}")
    generation = run.root / f"generations/transformation/iteration-{final[0]:03d}/generation.json"
    final_hash = sha256(final[1])
    if json.loads(generation.read_text(encoding="utf-8"))["output_artifact"]["sha256"] != final_hash:
        raise ValueError(f"final generation hash mismatch: {run.run_id}")
    observations = []
    for path in sorted((run.root / "observations/generated_transformations").rglob("suite_execution.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item["inputs"]["transformation"]["sha256"] == final_hash:
            observations.append({"path": str(path), "sha256": sha256(path), "observation": item["observation"]})
    syntax = [str(path) for path in sorted((run.root / "generations/transformation").glob("*/generation.json"))
        if (item := json.loads(path.read_text(encoding="utf-8"))).get("purpose") == "syntax_refinement"
        and int(item["iteration"]) > versions.semantic_iterations[0]]
    return {"run_id": run.run_id, "language": run.language, "task": run.task,
        "model": run.manifest.get("llm", run.manifest.get("model")), "run_root": str(run.root),
        "manifest": str(run.root / "manifest.json"), "terminal_result": str(run.root / "result.json"),
        "terminal_outcome": run.terminal_result["outcome_code"],
        "T0_iteration": versions.initial[0], "Tpre_iteration": versions.pre[0], "Tpost_iteration": final[0],
        "Tpre": str(versions.pre[1]), "Tpre_sha256": sha256(versions.pre[1]),
        "Tpost": str(final[1]), "Tpost_sha256": final_hash,
        "semantic_requests": [str(path) for path in versions.requests],
        "final_adopted": True, "final_semantically_evaluated": bool(observations),
        "final_execution_evidence": observations, "later_syntax_requests": syntax,
        "syntax_sensitivity_exclusion": bool(syntax)}


def with_context(task: LegacyTask, path: Path) -> LegacyTask:
    return replace(task, context_file=path)


def behavioral_outcome(rows: list[dict[str, Any]]) -> str:
    """Technical errors take precedence over semantic kills, never become kills."""
    behavior = [row for row in rows if row["strength"] == "behavioral"]
    if not behavior:
        return "UNAVAILABLE"
    for status in ("UNAVAILABLE", "INFRASTRUCTURE_ERROR", "COMPILATION_ERROR", "RUNTIME_ERROR"):
        if any(row["outcome"] == status for row in behavior):
            return status
    if any(not row["observed"] for row in behavior):
        return "INFRASTRUCTURE_ERROR"
    return "ASSERTION_FAILURE" if any(row["outcome"] == "ASSERTION_FAILURE" for row in behavior) else "PASS"


def qualified(rows: list[dict[str, Any]], negative: list[dict[str, Any]] | None = None) -> bool:
    if behavioral_outcome(rows) != "PASS":
        return False
    if negative is None:
        return True
    behavior = [row for row in negative if row["strength"] == "behavioral"]
    return all(row["observed"] and row["outcome"] not in ("COMPILATION_ERROR", "INFRASTRUCTURE_ERROR", "UNAVAILABLE")
               for row in behavior) and any(row["outcome"] != "PASS" for row in behavior)
