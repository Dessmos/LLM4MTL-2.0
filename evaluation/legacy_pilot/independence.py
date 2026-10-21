"""Inspect saved prompt evidence without asserting unavailable historical facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.legacy_pilot.assessment import selected_runs, sha256, task_mapping
from llm4mtl.paths import REPO_ROOT, TARGET


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [text for item in value for text in string_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in string_values(item)]
    return []


def historical_task_prompts() -> dict[str, Any]:
    """Recover changed task specifications by recorded SHA-256 and Git blobs."""
    missing = {}
    affected = []
    for run in selected_runs():
        path = run.root / "generations/transformation/iteration-000/generation.json"
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        current = TARGET.prompt_assets / "task_prompts" / run.language / (run.task + ".txt")
        recorded_hash = record["prompt"]["sha256"]
        if sha256(current) != recorded_hash:
            missing[recorded_hash] = run.task
            affected.append({"run_id": run.run_id, "recorded_sha256": recorded_hash})
    objects = subprocess.check_output(["git", "rev-list", "--objects", "--all"], cwd=REPO_ROOT, text=True).splitlines()
    recovered = {}
    for line in objects:
        oid, _, path = line.partition(" ")
        if not path.endswith(".txt") or not any(task.lower() in path.lower() for task in missing.values()):
            continue
        blob = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=REPO_ROOT)
        digest = hashlib.sha256(blob).hexdigest()
        if digest in missing:
            recovered[digest] = {"path": path, "git_blob": oid, "task": missing[digest], "content": blob.decode("utf-8")}
    return {"different_hash_count": len(missing), "affected_initial_runs": affected, "recovered": recovered,
            "unrecovered": {digest: task for digest, task in missing.items() if digest not in recovered}}


def inspect_independence() -> dict[str, Any]:
    """Scan actual saved refinement texts/requests and diagnosis request strings.

    Class names, method names and long Java assertion statements are signatures
    of direct legacy-code exposure. Shared specification values are not proof of
    code exposure. Missing initial assembled messages remain explicitly unknown.
    """
    mapping = task_mapping()
    classes = sorted({item.class_name for item in mapping})
    methods = sorted({case.method for item in mapping for case in item.cases})
    statements = set()
    for path in {item.java_file for item in mapping}:
        text = path.read_text(encoding="utf-8")
        for statement in re.findall(r"(?:Assertions\.)?assert\w+\s*\(.*?;", text, re.DOTALL):
            normalized = re.sub(r"\s+", "", statement)
            if len(normalized) >= 80:
                statements.add(normalized)
    signatures = classes + methods
    counters: Counter[str] = Counter()
    scanned = []
    matches = []
    request_inputs = Counter()
    for run in selected_runs():
        for path in sorted((run.root / "generations/transformation").glob("*/generation.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            counters["generation_" + record["purpose"]] += 1
            prompt = record.get("prompt") or {}
            if record["purpose"] == "initial":
                counters["initial_with_full_assembled_prompt_archived"] += int(
                    (run.root / "responses/transformation-generation/iteration-000/prompt.md").is_file())
                # This recorded hash identifies the frozen task specification,
                # not the complete n8n system/user messages.
                candidate = TARGET.prompt_assets / "task_prompts" / run.language / (run.task + ".txt")
                if candidate.is_file() and sha256(candidate) == prompt.get("sha256"):
                    counters["initial_task_prompt_matches_current_hash"] += 1
            else:
                actual = run.root / prompt["path"]
                if sha256(actual) != prompt["sha256"]:
                    raise ValueError(f"saved refinement prompt hash mismatch: {actual}")
                counters["verified_refinement_prompt_hashes"] += 1
        groups = [
            ("refinement_prompt", sorted((run.root / "refinements/transformation").glob("*/prompt.md"))),
            ("refinement_request", sorted((run.root / "refinements/transformation").glob("*/request.json"))),
            ("diagnosis_request", sorted((run.root / "responses/source-diagnosis").rglob("*diagnosis_request.json"))),
        ]
        for group, paths in groups:
            for path in paths:
                if path.suffix == ".json":
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    text = "\n".join(string_values(payload))
                    if group == "refinement_request":
                        context = payload["original_task_context"]
                        entries = [context["prompt"], *context["metamodels"], *context["supporting_files"],
                                   *payload["previous_artifact"]["files"]]
                        for entry in entries:
                            request_inputs[entry["path"]] += 1
                else:
                    text = path.read_text(encoding="utf-8")
                hits = [signature for signature in signatures if signature in text]
                normalized = re.sub(r"\s+", "", text)
                statement_hits = [statement for statement in statements if statement in normalized]
                counters[group] += 1
                scanned.append({"kind": group, "run_id": run.run_id, "path": str(path),
                                "sha256": sha256(path), "legacy_name_hits": hits,
                                "long_assertion_statement_hits": len(statement_hits)})
                if hits or statement_hits:
                    matches.append(scanned[-1])
    asset_paths = sorted(path for root in [TARGET.prompt_assets / "transformations", TARGET.prompt_assets / "task_prompts"]
                         for path in root.rglob("*") if path.is_file())
    asset_hits = []
    for path in asset_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        names = [signature for signature in signatures if signature in text]
        statements_found = sum(statement in re.sub(r"\s+", "", text) for statement in statements)
        if names or statements_found:
            asset_hits.append({"path": str(path), "name_hits": names, "assertion_hits": statements_found})
    construction = ["pipeline/src/llm4mtl/prompt_assembly/task_inputs.py",
                    "pipeline/src/llm4mtl/prompt_assembly/refinement.py",
                    "pipeline/src/llm4mtl/prompt_assembly/n8n_exports/prompts.py",
                    "pipeline/src/llm4mtl/prompt_assembly/n8n_exports/synchronizers.py",
                    "workflows/n8n/main/llm4mtl-agent-workflow.json"]
    return {"schema_version": "1.0", "counters": dict(counters),
        "legacy_classes": len(classes), "legacy_methods": len(methods),
        "long_assertion_signatures": len(statements), "matches": matches,
        "assets_scanned": len(asset_paths), "asset_matches": asset_hits,
        "direct_input_paths": dict(sorted(request_inputs.items())),
        "construction_files": [{"path": str(REPO_ROOT / path), "sha256": sha256(REPO_ROOT / path)} for path in construction],
        "scanned_artifacts": scanned,
        "limitations": ["initial full system/user requests are not proved by a task-prompt hash",
                        "current prompt-construction source cannot prove dirty historical workflow bytes",
                        "absence of textual signatures does not prove absence of paraphrased or indirect exposure",
                        "task specifications and reference-derived examples intentionally share behavior with legacy assertions"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--historical-output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("independence evidence must not overwrite an earlier report")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inspect_independence(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.historical_output is not None:
        if args.historical_output.exists():
            raise ValueError("historical evidence must not overwrite an earlier report")
        args.historical_output.parent.mkdir(parents=True, exist_ok=True)
        args.historical_output.write_text(json.dumps(historical_task_prompts(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
