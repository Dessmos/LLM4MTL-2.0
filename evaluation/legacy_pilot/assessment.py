"""Read-only population, endpoint and legacy-suite mapping for the pilot.

This supplementary assessment does not alter the campaign metrics defined in
docs/measurement-spec.md. Artifact availability is not an execution verdict.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evaluation._common import SelectedRun, transformation_iterations
from llm4mtl.paths import TARGET


@dataclass(frozen=True)
class LegacyCase:
    method: str
    strength: str


@dataclass(frozen=True)
class LegacyTask:
    language: str
    task: str
    java_file: Path
    cases: tuple[LegacyCase, ...]
    destination: str
    context_file: Path | None = None

    @property
    def class_name(self) -> str:
        return self.java_file.stem

    @property
    def selector(self) -> str:
        return self.class_name + "#" + "+".join(case.method for case in self.cases)


@dataclass(frozen=True)
class Endpoints:
    initial: tuple[int, Path]
    pre: tuple[int, Path] | None
    post: tuple[int, Path]
    semantic_iterations: tuple[int, ...]
    requests: tuple[Path, ...]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_runs() -> tuple[SelectedRun, ...]:
    """Use the twelve selected CSVs, never the discarded retry attempts."""
    runs: list[SelectedRun] = []
    for path in sorted((TARGET.artifacts / "Chosen_for_evaluation").rglob("batch-runs.csv")):
        with path.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                root = TARGET.run_dir(row["batch_id"], row["run_id"])
                manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
                result = json.loads((root / "result.json").read_text(encoding="utf-8"))
                if manifest["run_id"] != row["run_id"] or result["run_id"] != row["run_id"]:
                    raise ValueError(f"run identity mismatch: {root}")
                runs.append(SelectedRun(row["run_id"], root, manifest, result))
    if len(runs) != 564 or len({run.run_id for run in runs}) != 564:
        raise ValueError("selected population is not 564 distinct runs")
    return tuple(runs)


def endpoints(run: SelectedRun) -> Endpoints | None:
    """Tpre precedes the FIRST semantic repair; Tpost is the final saved version.

Syntax repairs after a semantic attempt remain in Tpost, and are reported in
the generation trajectory rather than attributed solely to semantic feedback.
"""
    if not list((run.root / "transformation").glob("iteration-*/metadata.json")):
        return None
    versions = dict(transformation_iterations(run))
    if sorted(versions) != list(range(max(versions) + 1)):
        raise ValueError(f"non-contiguous transformation versions: {run.run_id}")
    semantic: list[int] = []
    requests: list[Path] = []
    previous: int | None = None
    for path in sorted((run.root / "generations/transformation").glob("*/generation.json")):
        generation = json.loads(path.read_text(encoding="utf-8"))
        if generation.get("purpose") != "semantic_refinement":
            continue
        iteration = int(generation["iteration"])
        request_path = run.root / "refinements/transformation" / f"iteration-{iteration:03d}" / "request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if request["feedback"]["source"] != "semantic":
            raise ValueError(f"semantic purpose / feedback disagreement: {request_path}")
        pre = int(request["previous_iteration"])
        if pre != iteration - 1 or pre not in versions or iteration not in versions:
            raise ValueError(f"unrecoverable semantic endpoints: {request_path}")
        if generation["input_artifact_iteration"] != pre:
            raise ValueError(f"generation / request input disagreement: {path}")
        files = request["previous_artifact"]["files"]
        if len(files) != 1 or hashlib.sha256(files[0]["content"].encode("utf-8")).hexdigest() != sha256(versions[pre]):
            raise ValueError(f"prepared prompt does not contain the stored Tpre: {request_path}")
        if previous is None:
            previous = pre
        semantic.append(iteration)
        requests.append(request_path)
    final = max(versions)
    initial_generation = json.loads((run.root / "generations/transformation/iteration-000/generation.json").read_text(encoding="utf-8"))
    if initial_generation["purpose"] != "initial" or initial_generation["output_artifact"]["sha256"] != sha256(versions[0]):
        raise ValueError(f"stored T0 differs from initial generated output: {run.run_id}")
    return Endpoints((0, versions[0]), None if previous is None else (previous, versions[previous]),
                     (final, versions[final]), tuple(semantic), tuple(requests))


def java_test_methods(path: Path) -> tuple[str, ...]:
    text = path.read_text(encoding="utf-8")
    return tuple(re.findall(r"@Test\b(?:(?!@Test).)*?\bvoid\s+(\w+)\s*\(", text, re.DOTALL))


def task_mapping() -> tuple[LegacyTask, ...]:
    """Map all 47 tasks to existing methods without changing Java assertions."""
    mapping: list[LegacyTask] = []
    atl = TARGET.engine_harness("atl") / "src/test/java/org/example"
    for path in sorted(atl.glob("*ExecutionTest.java")):
        task = path.stem.removesuffix("AllExecutionTest") + "_All"
        mapping.append(LegacyTask("atl", task, path,
            tuple(LegacyCase(name, "behavioral") for name in java_test_methods(path)),
            f"src/main/atl/{task}.atl"))
    etl = TARGET.engine_harness("etl") / "src/test/java/org/eclipse/epsilon/examples/etl"
    names = {"Tree2GraphTest": "Tree2Graph", "OO2DBTest": "OO2DB", "Rss2AtomTest": "rss2atom",
             "BaseTest": "base", "EquivalentTest": "equivalent", "GreedyTest": "greedy",
             "InheritanceTest": "inheritance", "LazyTest": "lazy",
             "MultipleTargetsTest": "multiple_targets", "PrimaryTest": "primary"}
    for path in sorted(etl.rglob("*Test.java")):
        task = names[path.stem]
        mapping.append(LegacyTask("etl", task, path,
            tuple(LegacyCase(name, "behavioral") for name in java_test_methods(path)),
            f"src/test/resources/transformations/{task}.etl"))
    qvto = TARGET.engine_harness("qvto") / "qvto-tests/actual/src/test/java/org/eclipse/qvto/tests"
    for path in sorted(qvto.glob("*Test.java")):
        task = path.stem.removesuffix("Test")
        cases = tuple(LegacyCase(name, "resource_smoke" if name == "transformationLoadsSuccessfully"
                                else "execution_smoke" if name == "executesSuccessfully"
                                else "behavioral") for name in java_test_methods(path))
        mapping.append(LegacyTask("qvto", task, path, cases,
            f"qvto-tests/actual/src/main/resources/transformations/{task}.qvto"))
    reactions = TARGET.engine_harness("reactions")
    java = reactions / "vsum/src/test/java/tools/vitruv/methodologisttemplate/vsum"
    context_root = reactions / "consistency/src/main/reactions/tools/vitruv/methodologisttemplate/consistency"
    definitions = (
        ("FamiliesToPersons_InsertedFamilyRegister", "FamiliesPersonsTest", "familyPersons", ("insertFamilyRegisterCreatesPersonRegister",)),
        ("FamiliesToPersons_CreatedFather", "FamiliesPersonsTest", "familyPersons", ("createdFatherCreatesPersonAndNamesAreCorrect", "createdNewFatherRemovesOldFather")),
        ("FamiliesToPersons_InsertedDaughter", "FamiliesPersonsTest", "familyPersons", ("insertedDaughterCreatesPersonAndNamesAreCorrect",)),
        ("FamiliesToPersons_DeletedMember", "FamiliesPersonsTest", "familyPersons", ("deleteFatherDeletesCorrespondingPerson",)),
        ("FamiliesToPersons_DeletedFamily", "FamiliesPersonsTest", "familyPersons", ("deleteFamilyDeletesCorrespondingPersons",)),
        ("NetworkToGraph_CreateAndRegisterRoot", "NetworkGraphTest", "networkGraph", ("systemInsertionAndPropagationTest",)),
        ("NetworkToGraph_ComponentInsertedIntoSystem", "NetworkGraphTest", "networkGraph", ("insertComponent",)),
        ("NetworkToGraph_ComponentRenamed", "NetworkGraphTest", "networkGraph", ("renameComponent",)),
        ("NetworkToGraph_ComponentDeleted", "NetworkGraphTest", "networkGraph", ("deleteComponent",)),
        ("AmaltheaToAscet_ComponentContainerInsertedAsRoot", "AmaltheaAscetTest", "amaltheaAscet", ("ComponentContainerInsertedAsRootCreatesRootcomponentcontainer",)),
        ("AmaltheaToAscet_TaskCreated", "AmaltheaAscetTest", "amaltheaAscet", ("InterruptTaskCreatedCreatesAscetModule", "PeriodicTaskCreatedCreatesAscetModule", "UncorrectTaskNumberCreatesNoAscetModule")),
        ("AmaltheaToAscet_TaskDeleted", "AmaltheaAscetTest", "amaltheaAscet", ("TaskDeletedRemovesCorrespondingAscetTask",)),
    )
    for task, cls, context, methods in definitions:
        context_file = context_root / f"{context}.reactions"
        cases = tuple(LegacyCase(name, "source_only_weak" if name == "createdNewFatherRemovesOldFather"
                                else "behavioral") for name in methods)
        path = java / f"{cls}.java"
        if not set(methods).issubset(java_test_methods(path)):
            raise ValueError(f"legacy methods missing: {task}")
        mapping.append(LegacyTask("reactions", task, path, cases,
                                  str(context_file.relative_to(reactions)), context_file))
    if len(mapping) != 47 or len({(item.language, item.task) for item in mapping}) != 47:
        raise ValueError("legacy mapping does not cover 47 distinct tasks")
    return tuple(mapping)


def mapping_records(mapping: tuple[LegacyTask, ...]) -> list[dict[str, Any]]:
    return [{"language": task.language, "task": task.task, "java_file": str(task.java_file),
             "java_sha256": sha256(task.java_file), "class": task.class_name,
             "method": case.method, "strength": case.strength,
             "destination": task.destination,
             "context": None if task.context_file is None else str(task.context_file),
             "reference": str(TARGET.benchmark / "tasks" / task.language / "references" /
                              (task.task + {"atl": ".atl", "etl": ".etl", "qvto": ".qvto", "reactions": ".reactions"}[task.language]))}
            for task in mapping for case in task.cases]


def population_records(runs: tuple[SelectedRun, ...]) -> list[dict[str, Any]]:
    rows = []
    for run in runs:
        ends = endpoints(run)
        rows.append({"run_id": run.run_id, "language": run.language, "task": run.task,
            "run_root": str(run.root), "artifacts_present": ends is not None,
            "T0": "" if ends is None else str(ends.initial[1]),
            "Tpre": "" if ends is None or ends.pre is None else str(ends.pre[1]),
            "Tpost": "" if ends is None else str(ends.post[1]),
            "T0_iteration": "" if ends is None else ends.initial[0],
            "Tpre_iteration": "" if ends is None or ends.pre is None else ends.pre[0],
            "Tpost_iteration": "" if ends is None else ends.post[0],
            "semantic_iterations": "" if ends is None else ";".join(map(str, ends.semantic_iterations)),
            "semantic_refined": ends is not None and bool(ends.semantic_iterations),
            "Tpre_equals_T0": "" if ends is None or ends.pre is None else ends.pre[0] == 0,
            "syntax_after_first_semantic": "" if ends is None or not ends.semantic_iterations else any(
                json.loads(p.read_text(encoding="utf-8")).get("purpose") == "syntax_refinement"
                and int(json.loads(p.read_text(encoding="utf-8"))["iteration"]) > ends.semantic_iterations[0]
                for p in (run.root / "generations/transformation").glob("*/generation.json"))})
    return rows
