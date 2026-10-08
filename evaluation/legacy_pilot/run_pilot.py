"""Execute four explicitly selected legacy-suite feasibility cases, not a campaign.

Run with PYTHONPATH=pipeline/src .venv/bin/python -m
evaluation.legacy_pilot.run_pilot --output <new-directory>. All Maven work is
temporary; detailed command, source, environment and Surefire evidence survives
in the separate output directory. No production adapter or artifact is changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from evaluation.legacy_pilot.assessment import (
    LegacyTask, endpoints, mapping_records, population_records,
    selected_runs, sha256, task_mapping,
)
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.workspace import materialize_engine


# Chosen before any legacy execution: first batch-014 run for each named task,
# with semantic repair and a behavioral legacy method. ATL, ETL and Reactions
# additionally exercise the distinction between T0 and syntax-repaired Tpre.
PILOT_TASKS = {"atl": "CPL2SPL_All", "etl": "inheritance",
               "qvto": "MappingExtensionMerges", "reactions": "FamiliesToPersons_CreatedFather"}
MUTANT_IDS = ("M1", "M4")
DECLARATION = re.compile(r"^[ \t]*(reaction|routine)\s+(\w+)\b", re.MULTILINE)


@dataclass(frozen=True)
class SourceBlock:
    kind: str
    name: str
    start: int
    end: int
    text: str


def source_blocks(source: str) -> tuple[SourceBlock, ...]:
    """Read top-level Reactions bodies; braces in strings/comments are ignored."""
    blocks = []
    for match in DECLARATION.finditer(source):
        opening = source.index("{", match.end())
        depth = 0
        quote = ""
        comment = ""
        index = opening
        while index < len(source):
            ch = source[index]
            pair = source[index:index + 2]
            if comment == "line":
                if ch == "\n":
                    comment = ""
            elif comment == "block":
                if pair == "*/":
                    comment = ""
                    index += 1
            elif quote:
                if ch == "\\":
                    index += 1
                elif ch == quote:
                    quote = ""
            elif pair in ("//", "/*"):
                comment = "line" if pair == "//" else "block"
                index += 1
            elif ch in ('"', "'"):
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(SourceBlock(match.group(1), match.group(2), match.start(),
                                              index + 1, source[match.start():index + 1]))
                    break
            index += 1
        else:
            raise ValueError(f"unclosed {match.group(1)} {match.group(2)}")
    names = [(block.kind, block.name) for block in blocks]
    if len(names) != len(set(names)):
        raise ValueError("duplicate Reactions declarations")
    return tuple(blocks)


def compose_reactions(context: str, reference: str, candidate: str | None) -> tuple[str, dict[str, Any]]:
    """Replace only a task's reaction/routines in its fixed full legacy context.

The segment and original metamodel aliases stay fixed, so unmodified Java
tests instantiate exactly the same specification. Collisions with background
logic cause a recorded preparation error rather than silently replacing it.
"""
    targets = {(block.kind, block.name) for block in source_blocks(reference)}
    context_blocks = source_blocks(context)
    present = {(block.kind, block.name) for block in context_blocks}
    if not targets.issubset(present):
        raise ValueError(f"task declarations missing from context: {targets - present}")
    background = [block for block in context_blocks if (block.kind, block.name) not in targets]
    injected = () if candidate is None else source_blocks(candidate)
    if candidate is not None and sum(block.kind == "reaction" for block in injected) != 1:
        raise ValueError("pilot candidate must contain exactly one reaction")
    collisions = {(block.kind, block.name) for block in injected} & {
        (block.kind, block.name) for block in background}
    if collisions:
        raise ValueError(f"candidate collides with fixed background declarations: {collisions}")
    if candidate is not None:
        original_imports = set(re.findall(r'^import\s+.*$', context, re.MULTILINE))
        candidate_imports = set(re.findall(r'^import\s+.*$', candidate, re.MULTILINE))
        if not candidate_imports.issubset(original_imports):
            raise ValueError("candidate imports differ from fixed legacy metamodel context")
    prepared = context
    for block in reversed(context_blocks):
        if (block.kind, block.name) in targets:
            prepared = prepared[:block.start] + prepared[block.end:]
    prepared = prepared.rstrip() + "\n\n" + "\n\n".join(block.text for block in injected) + "\n"
    rebuilt = {(block.kind, block.name): block.text for block in source_blocks(prepared)}
    if any(rebuilt[(block.kind, block.name)] != block.text for block in background):
        raise ValueError("background changed during composition")
    facts = {"removed_declarations": sorted(f"{kind}:{name}" for kind, name in targets),
             "candidate_declarations": [f"{block.kind}:{block.name}" for block in injected],
             "background_sha256": hashlib.sha256("\n".join(block.text for block in background).encode()).hexdigest(),
             "background_unchanged": True, "segment": re.search(r"^reactions:\s*(\w+)", context, re.MULTILINE).group(1)}
    return prepared, facts


def classify_failure(kind: str, exception_type: str, message: str, stack: str) -> str:
    """Conservatively separate framework/pre-assertion failures from behavior."""
    text = message + "\n" + stack
    if re.search(r"Resource not found|Transformation not found|input.*not found|ATL file not found", text, re.IGNORECASE):
        return "INFRASTRUCTURE_ERROR"
    if re.search(r"Syntax error|parse error|Parser problems|compilation error|Compiled ASM file is empty|TransformationExecutor\.load", text, re.IGNORECASE):
        return "COMPILATION_ERROR"
    if "QvtoTestBase.executeTransformation" in stack or "Transformation failed:" in message:
        return "RUNTIME_ERROR"
    if "compileAtl(" in stack:
        return "COMPILATION_ERROR"
    if kind == "failure" and ("AssertionFailedError" in exception_type or "AssertionError" in exception_type):
        return "ASSERTION_FAILURE"
    return "RUNTIME_ERROR"


def classify_build(output: str) -> str:
    if re.search(r"Could not resolve|Cannot access|offline mode|Non-resolvable|No plugin found|Connection refused|UnknownHost|Could not transfer|No tests matching|No tests were executed", output, re.IGNORECASE):
        return "INFRASTRUCTURE_ERROR"
    if re.search(r"COMPILATION ERROR|Compilation failure|maven-compiler-plugin.*failed|Error compiling|Xtext.*errors|Couldn't resolve reference|severe validation error|Invalid number of arguments", output, re.IGNORECASE):
        return "COMPILATION_ERROR"
    return "INFRASTRUCTURE_ERROR"


def semantic_kill(reference_rows: list[dict[str, Any]], mutant_rows: list[dict[str, Any]]) -> bool:
    """No technical error anywhere; only a reference-passing behavioral failure kills."""
    if not reference_rows or any(row["outcome"] != "PASS" or not row["observed"] for row in reference_rows):
        return False
    if any(row["outcome"] not in ("PASS", "ASSERTION_FAILURE") or not row["observed"] for row in mutant_rows):
        return False
    passed = {row["method"] for row in reference_rows if row["strength"] == "behavioral"}
    return any(row["method"] in passed and row["strength"] == "behavioral"
               and row["outcome"] == "ASSERTION_FAILURE" for row in mutant_rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def tree_hashes(root: Path, excluded: str | None = None) -> dict[str, str]:
    return {str(path.relative_to(root)): sha256(path) for path in sorted(root.rglob("*"))
            if path.is_file() and "target" not in path.relative_to(root).parts
            and ".git" not in path.relative_to(root).parts
            and str(path.relative_to(root)) != excluded}


def command_configuration(task: LegacyTask, engine: Path, repository: Path) -> tuple[list[str], Path]:
    command = ["mvn", "-o", "-B", "-ntp", f"-Dmaven.repo.local={repository}", "clean", "test",
               f"-Dtest={task.selector}", "-Dsurefire.failIfNoSpecifiedTests=false"]
    cwd = engine
    if task.language == "qvto":
        cwd = engine / "qvto-tests"
        command += ["-pl", "actual", "-am"]
    elif task.language == "reactions":
        command += ["-pl", "vsum", "-am"]
    return command, cwd


def runtime_classpath_hashes(report_paths: list[Path], repository: Path) -> dict[str, str]:
    hashes = {}
    for path in report_paths:
        for prop in ET.parse(path).getroot().findall("./properties/property"):
            if prop.get("name") not in ("java.class.path", "surefire.test.class.path"):
                continue
            for entry in prop.get("value", "").split(os.pathsep):
                jar = Path(entry)
                if jar.is_file() and jar.suffix == ".jar" and jar.is_relative_to(repository):
                    hashes[str(jar.relative_to(repository))] = sha256(jar)
    return hashes


def execute_trial(task: LegacyTask, label: str, source: Path | None, reference: Path,
                  workspace_root: Path, repository: Path, output: Path, timeout: int) -> dict[str, Any]:
    trial = output / task.language / label
    trial.mkdir(parents=True)
    engine = materialize_engine(TARGET.engine_harness(task.language), workspace_root, task.language + "-" + label)
    destination = engine / task.destination
    composition = None
    source_text = "" if source is None else source.read_text(encoding="utf-8")
    # This existing production compatibility adjustment is identical for every
    # Reactions endpoint; the frozen template and test sources stay untouched.
    adjustments = []
    if task.language == "reactions":
        pom = engine / "consistency/pom.xml"
        tree = ET.parse(pom)
        ns = "{http://maven.apache.org/POM/4.0.0}"
        deps = tree.getroot().find(ns + "dependencies")
        for dependency in list(deps):
            if dependency.findtext(ns + "artifactId") == "edu.kit.ipd.sdq.metamodels.families":
                deps.remove(dependency)
                adjustments.append("removed unused unpublished sdq-demo-metamodels families dependency in temporary copy")
        ET.register_namespace("", ns[1:-1])
        tree.write(pom, encoding="UTF-8", xml_declaration=True)
    preparation_error = ""
    try:
        if task.context_file is not None:
            source_text, composition = compose_reactions(task.context_file.read_text(encoding="utf-8"),
                reference.read_text(encoding="utf-8"), None if source is None else source_text)
        destination.write_text(source_text, encoding="utf-8")
    except ValueError as exc:
        preparation_error = str(exc)
    (trial / ("candidate" + reference.suffix)).write_text(source_text, encoding="utf-8")
    invariant = tree_hashes(engine, task.destination)
    write_json(trial / "fixed-input-hashes.json", invariant)
    command, cwd = command_configuration(task, engine, repository)
    env = dict(os.environ)
    env["MAVEN_OPTS"] = "-Xmx768m -Dfile.encoding=UTF-8 -Duser.language=en -Duser.country=US"
    started = time.monotonic()
    timed_out = False
    stdout = stderr = ""
    if preparation_error:
        exit_code = -1
        stderr = preparation_error
    else:
        try:
            result = subprocess.run(command, cwd=cwd, env=env, text=True,
                                    capture_output=True, timeout=timeout)
            exit_code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = (exc.stdout or b"").decode("utf-8", errors="replace")
            stderr = (exc.stderr or b"").decode("utf-8", errors="replace")
            timed_out = True
    duration = time.monotonic() - started
    (trial / "stdout.log").write_text(stdout, encoding="utf-8")
    (trial / "stderr.log").write_text(stderr, encoding="utf-8")
    reports = sorted(engine.rglob("target/surefire-reports/TEST-*.xml"))
    observed = {}
    for path in reports:
        relative = path.relative_to(engine)
        archived = trial / "reports" / relative
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, archived)
        for case in ET.parse(path).getroot().iter("testcase"):
            if not case.get("classname", "").endswith(task.class_name):
                continue
            method = case.get("name", "").split("(", 1)[0]
            if method not in {item.method for item in task.cases}:
                continue
            failure = case.find("failure")
            error = case.find("error")
            node = failure if failure is not None else error
            if case.find("skipped") is not None:
                outcome, detail = "INFRASTRUCTURE_ERROR", "JUnit skipped"
            elif node is None:
                outcome, detail = "PASS", ""
            else:
                detail = node.get("message", "") + "\n" + (node.text or "")
                outcome = classify_failure("failure" if failure is not None else "error",
                    node.get("type", ""), node.get("message", ""), node.text or "")
            observed[method] = (outcome, detail)
    if preparation_error:
        fallback = "COMPILATION_ERROR" if re.search(r"unclosed|duplicate Reactions declarations", preparation_error) else "INFRASTRUCTURE_ERROR"
    else:
        fallback = classify_build(stdout + "\n" + stderr)
    rows = [{"language": task.language, "task": task.task, "label": label,
             "class": task.class_name, "method": case.method, "strength": case.strength,
             "observed": case.method in observed,
             "outcome": observed.get(case.method, (fallback, ""))[0],
             "detail": observed.get(case.method, ("", stderr if preparation_error else "method not reached; see Maven log"))[1]}
            for case in task.cases]
    facts = {"language": task.language, "task": task.task, "label": label,
        "source": None if source is None else str(source), "source_sha256": None if source is None else sha256(source),
        "prepared_sha256": sha256(destination) if not preparation_error else None,
        "command": command, "cwd": str(cwd), "duration_seconds": duration,
        "exit_code": exit_code, "timed_out": timed_out, "preparation_error": preparation_error,
        "adjustments": adjustments, "composition": composition,
        "fixed_inputs_digest": hashlib.sha256(json.dumps(invariant, sort_keys=True).encode()).hexdigest(),
        "runtime_dependencies": runtime_classpath_hashes(reports, repository),
        "environment": {"MAVEN_OPTS": env["MAVEN_OPTS"], "offline": True}, "methods": rows}
    write_json(trial / "execution.json", facts)
    write_csv(trial / "methods.csv", rows)
    print(json.dumps({"language": task.language, "label": label, "duration": round(duration, 2),
                      "outcomes": [row["outcome"] for row in rows]}, sort_keys=True), flush=True)
    return facts


def language_trials(task: LegacyTask, run: Any, mutants: list[dict[str, Any]],
                    workspace_root: Path, repository: Path, output: Path, timeout: int) -> list[dict[str, Any]]:
    versions = endpoints(run)
    if versions is None or versions.pre is None:
        raise ValueError(f"pilot run lacks semantic pair: {run.run_id}")
    reference = TARGET.benchmark / "tasks" / task.language / "references" / (task.task + versions.initial[1].suffix)
    sources = [("reference", reference), ("Tpre", versions.pre[1]), ("Tpost", versions.post[1])]
    sources.extend(("mutant-" + mutant["mutant"], REPO_ROOT / mutant["file"]) for mutant in mutants)
    if task.language == "reactions":
        sources.append(("candidate-absent-control", None))
    executions = [execute_trial(task, label, source, reference, workspace_root,
                  repository, output, timeout) for label, source in sources]
    invariants = {execution["fixed_inputs_digest"] for execution in executions}
    if len(invariants) != 1:
        raise ValueError(f"fixed engine inputs differ across trials: {task.language}")
    dependencies = [execution["runtime_dependencies"] for execution in executions if execution["runtime_dependencies"]]
    if dependencies and any(deps != dependencies[0] for deps in dependencies):
        raise ValueError(f"resolved runtime dependencies differ across trials: {task.language}")
    return executions


def minimal_reactions_context(task: LegacyTask, output: Path) -> LegacyTask:
    """Fix the target's legacy segment to the contract prerequisite closure.

    This removes unused reactions before every trial, not in response to an
    endpoint result. The retained blocks are exact original legacy source.
    """
    context = task.context_file.read_text(encoding="utf-8")
    target_reference = TARGET.benchmark / "tasks/reactions/references" / (task.task + ".reactions")
    prerequisite = TARGET.benchmark / "tasks/reactions/references/FamiliesToPersons_InsertedFamilyRegister.reactions"
    allowed = {(block.kind, block.name) for path in (target_reference, prerequisite)
               for block in source_blocks(path.read_text(encoding="utf-8"))}
    blocks = source_blocks(context)
    result = context
    for block in reversed(blocks):
        if (block.kind, block.name) not in allowed:
            result = result[:block.start] + result[block.end:]
    path = output / "fixed-reactions-context.reactions"
    path.write_text(result, encoding="utf-8")
    write_json(output / "reactions-context-definition.json", {
        "original_context": str(task.context_file), "original_sha256": sha256(task.context_file),
        "minimal_context": str(path), "minimal_sha256": sha256(path),
        "retained_declarations": sorted(f"{kind}:{name}" for kind, name in allowed),
        "reason": "only the fixed root-registration prerequisite and candidate task; unchanged original Java cases",
        "unused_background_removed_identically_before_all_trials": True})
    return replace(task, context_file=path)


def run_pilot(output: Path, timeout: int, languages: tuple[str, ...], reactions_context: str) -> None:
    if output.exists():
        raise ValueError("output must be a new directory; previous evidence is never overwritten")
    forbidden = [TARGET.runs, TARGET.benchmark, TARGET.engines,
                 TARGET.artifacts / "Chosen_for_evaluation", REPO_ROOT / "evaluation/mutants"]
    if any(output.is_relative_to(path) for path in forbidden):
        raise ValueError("pilot output may not be inside protected inputs")
    runs = selected_runs()
    mapping = task_mapping()
    population = population_records(runs)
    tasks = [task for task in mapping if PILOT_TASKS.get(task.language) == task.task and task.language in languages]
    selection = {task.language: next(run for run in runs if run.language == task.language
        and run.task == task.task and run.root.parent.name == "batch_014") for task in tasks}
    catalog_path = REPO_ROOT / "evaluation/mutants/manifest.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    mutations = {task.language: [mutant for mutant in catalog["mutants"]
        if mutant["language"].lower() == task.language and mutant["task"] == task.task
        and mutant["mutant"] in MUTANT_IDS and mutant["status"] == "PRESENT"] for task in tasks}
    if any(len(mutants) != 2 for mutants in mutations.values()):
        raise ValueError("each pilot task must have the two selected existing mutants")
    protected = {}
    for task in tasks:
        run = selection[task.language]
        versions = endpoints(run)
        for path in [task.java_file, versions.initial[1], versions.pre[1], versions.post[1],
                     TARGET.benchmark / "tasks" / task.language / "references" / (task.task + versions.initial[1].suffix),
                     *versions.requests, *[REPO_ROOT / mutant["file"] for mutant in mutations[task.language]]]:
            protected[str(path)] = sha256(path)
        for mutant in mutations[task.language]:
            if sha256(REPO_ROOT / mutant["file"]) != mutant["mutant_sha256"]:
                raise ValueError(f"catalog mutant hash mismatch: {mutant['file']}")
    output.mkdir(parents=True)
    if reactions_context == "minimal":
        tasks = [minimal_reactions_context(task, output) if task.language == "reactions" else task for task in tasks]
    write_csv(output / "task-test-mapping.csv", mapping_records(mapping))
    write_csv(output / "population.csv", population)
    environment = {}
    for name, command in [("java", ["java", "-version"]), ("maven", ["mvn", "-version"])]:
        version = subprocess.run(command, capture_output=True, text=True, timeout=30)
        environment[name] = version.stdout + version.stderr
    selection_records = [{"language": task.language, "task": task.task, "run_id": selection[task.language].run_id,
        "run_root": str(selection[task.language].root),
        "endpoints": next(row for row in population if row["run_id"] == selection[task.language].run_id),
        "mutants": mutations[task.language]} for task in tasks]
    write_json(output / "pilot-manifest.json", {"schema_version": "1.0", "commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip(),
        "selection_rule": "fixed named tasks; batch_014; selected before legacy execution; no outcome-based replacements",
        "environment": environment, "catalog_sha256": sha256(catalog_path), "tasks": selection_records,
        "reactions_context": reactions_context,
        "runner_sha256": sha256(REPO_ROOT / "evaluation/legacy_pilot/run_pilot.py"),
        "protected_input_hashes": protected, "timeout_seconds": timeout})
    implementation = output / "implementation"
    implementation.mkdir()
    for filename in ("assessment.py", "run_pilot.py"):
        shutil.copy2(REPO_ROOT / "evaluation/legacy_pilot" / filename, implementation / filename)
    with tempfile.TemporaryDirectory(prefix="llm4mtl-legacy-pilot-") as scratch:
        scratch_root = Path(scratch)
        repository = scratch_root / "maven-repository"
        shutil.copytree(Path.home() / ".m2/repository", repository)
        cache_before = {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")}
        write_json(output / "maven-cache-jar-hashes.json", cache_before)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(language_trials, task, selection[task.language], mutations[task.language],
                       scratch_root / "workspaces", repository, output, timeout) for task in tasks]
            executions = [trial for future in futures for trial in future.result()]
        cache_after = {str(path.relative_to(repository)): sha256(path) for path in repository.rglob("*.jar")}
        write_json(output / "maven-cache-check.json", {"jars_unchanged": cache_before == cache_after,
            "before_count": len(cache_before), "after_count": len(cache_after)})
        if cache_before != cache_after:
            raise ValueError("offline Maven cache JARs changed")
    mutation_rows = []
    for task in tasks:
        reference = next(trial for trial in executions if trial["language"] == task.language and trial["label"] == "reference")
        for trial in executions:
            if trial["language"] == task.language and trial["label"].startswith("mutant-"):
                mutation_rows.append({"language": task.language, "task": task.task, "mutant": trial["label"],
                    "semantic_kill": semantic_kill(reference["methods"], trial["methods"]),
                    "reference_passed": all(row["outcome"] == "PASS" for row in reference["methods"]),
                    "outcomes": ";".join(row["outcome"] for row in trial["methods"])})
    write_csv(output / "mutation-outcomes.csv", mutation_rows)
    write_csv(output / "method-outcomes.csv", [row for trial in executions for row in trial["methods"]])
    write_json(output / "executions.json", executions)
    unchanged = all(sha256(Path(path)) == digest for path, digest in protected.items())
    write_json(output / "protected-input-check.json", {"all_unchanged": unchanged, "file_count": len(protected)})
    if not unchanged:
        raise ValueError("protected pilot inputs changed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--languages", nargs="+", choices=tuple(PILOT_TASKS), default=list(PILOT_TASKS))
    parser.add_argument("--reactions-context", choices=("full", "minimal"), default="minimal")
    args = parser.parse_args()
    run_pilot(args.output.resolve(), args.timeout, tuple(args.languages), args.reactions_context)


if __name__ == "__main__":
    main()
