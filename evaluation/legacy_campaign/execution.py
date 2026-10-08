from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from evaluation.legacy_pilot.assessment import LegacyTask, sha256
from evaluation.legacy_pilot.run_pilot import (
    classify_build, classify_failure, command_configuration, compose_reactions,
    runtime_classpath_hashes, source_blocks, tree_hashes, write_csv, write_json,
)
from llm4mtl.paths import TARGET
from llm4mtl.workspace import materialize_engine


def prepare_reactions(context: str, reference: str, candidate: str, negative: bool) -> tuple[str, dict[str, Any]]:
    if not negative:
        return compose_reactions(context, reference, candidate)
    # Preserve every routine to avoid artificial unresolved-call compilation errors.
    target_names = {block.name for block in source_blocks(reference) if block.kind == "reaction"}
    result = context
    for block in reversed(source_blocks(context)):
        if block.kind == "reaction" and block.name in target_names:
            result = result[:block.start] + result[block.end:]
    return result, {"negative_control": "removed target reaction only; every routine retained",
        "removed_reactions": sorted(target_names), "background_unchanged": True}


def invoke(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    """Bound Maven and its children; persist both streams and timeout separately."""
    environment = dict(os.environ)
    environment.update(TZ="UTC", LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8",
        MAVEN_OPTS="-Xmx768m -Dfile.encoding=UTF-8 -Duser.language=en -Duser.country=US -Duser.timezone=UTC")
    started = time.monotonic()
    with subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", start_new_session=True) as process:
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr,
            "timed_out": timed_out, "duration_seconds": time.monotonic() - started,
            "environment": {key: environment[key] for key in ("TZ", "LANG", "LC_ALL", "MAVEN_OPTS")}}


def execute(task: LegacyTask, job: dict[str, Any], repository: Path, output: Path, timeout: int) -> dict[str, Any]:
    """One immutable attempt, with an isolated template and complete raw evidence."""
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="legacy-campaign-job-") as temporary:
        engine = materialize_engine(TARGET.engine_harness(task.language), Path(temporary), "engine")
        destination = engine / task.destination
        reference = Path(job["reference"])
        candidate = Path(job["source"])
        candidate_text = candidate.read_text(encoding="utf-8")
        adjustments = []
        if task.language == "reactions":
            pom = engine / "consistency/pom.xml"
            tree = ET.parse(pom)
            ns = "{http://maven.apache.org/POM/4.0.0}"
            deps = tree.getroot().find(ns + "dependencies")
            for dependency in list(deps):
                if dependency.findtext(ns + "artifactId") == "edu.kit.ipd.sdq.metamodels.families":
                    deps.remove(dependency)
                    adjustments.append("removed unused unpublished families dependency from temporary POM, as production adapter does")
            ET.register_namespace("", ns[1:-1])
            tree.write(pom, encoding="UTF-8", xml_declaration=True)
        preparation_error = ""
        composition = None
        try:
            if task.context_file is not None:
                candidate_text, composition = prepare_reactions(task.context_file.read_text(encoding="utf-8"),
                    reference.read_text(encoding="utf-8"), candidate_text, job["role"] == "negative")
            destination.write_text(candidate_text, encoding="utf-8")
        except (ValueError, IndexError) as error:
            preparation_error = str(error)
        (output / ("candidate" + reference.suffix)).write_text(candidate_text, encoding="utf-8")
        fixed = tree_hashes(engine, task.destination)
        write_json(output / "fixed-input-hashes.json", fixed)
        command, cwd = command_configuration(task, engine, repository)
        observation = {"stdout": "", "stderr": preparation_error, "exit_code": -1,
            "timed_out": False, "duration_seconds": 0, "environment": {}}
        if not preparation_error:
            observation = invoke(command, cwd, timeout)
        (output / "stdout.log").write_text(observation.pop("stdout"), encoding="utf-8")
        (output / "stderr.log").write_text(observation.pop("stderr"), encoding="utf-8")
        logs = (output / "stdout.log").read_text(encoding="utf-8") + (output / "stderr.log").read_text(encoding="utf-8")
        reports = sorted(engine.rglob("target/surefire-reports/TEST-*.xml"))
        observed = {}
        duplicates = []
        for report in reports:
            archive = output / "reports" / report.relative_to(engine)
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report, archive)
            for case in ET.parse(report).getroot().iter("testcase"):
                if not case.get("classname", "").endswith("." + task.class_name):
                    continue
                method = case.get("name", "").split("(", 1)[0]
                if method not in {item.method for item in task.cases}:
                    continue
                if method in observed:
                    duplicates.append(method)
                failure, error = case.find("failure"), case.find("error")
                node = failure if failure is not None else error
                if case.find("skipped") is not None:
                    status, detail = "INFRASTRUCTURE_ERROR", "JUnit skipped"
                elif node is None:
                    status, detail = "PASS", ""
                else:
                    status = classify_failure("failure" if failure is not None else "error",
                        node.get("type", ""), node.get("message", ""), node.text or "")
                    detail = node.get("message", "") + "\n" + (node.text or "")
                observed[method] = (status, detail)
        fallback = classify_build(logs)
        if preparation_error:
            fallback = "COMPILATION_ERROR" if re.search(r"unclosed|duplicate", preparation_error) else "INFRASTRUCTURE_ERROR"
        if observation["timed_out"] or duplicates:
            fallback = "INFRASTRUCTURE_ERROR"
            observed = {}
        rows = [{"job_id": job["job_id"], "run_id": job.get("run_id", ""), "language": task.language,
            "task": task.task, "role": job["role"], "context": job["context"],
            "operator": job.get("operator", ""), "class": task.class_name, "method": case.method,
            "strength": case.strength, "observed": case.method in observed,
            "outcome": observed.get(case.method, (fallback, ""))[0],
            "detail": observed.get(case.method, ("", preparation_error or "method not reached; see Maven log"))[1]}
            for case in task.cases]
        facts = {"job": job, **observation, "command": command, "cwd": str(cwd),
            "source_sha256": sha256(candidate), "prepared_sha256": None if preparation_error else sha256(destination),
            "preparation_error": preparation_error, "adjustments": adjustments, "composition": composition,
            "fixed_inputs_digest": hashlib.sha256(json.dumps(fixed, sort_keys=True).encode()).hexdigest(),
            "runtime_dependencies": runtime_classpath_hashes(reports, repository), "duplicate_methods": duplicates,
            "methods": rows}
        write_json(output / "execution.json", facts)
        write_csv(output / "methods.csv", rows)
        return facts
