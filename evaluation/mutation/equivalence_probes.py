"""Supplementary counterexamples; original suites and mutation definitions stay fixed.

These assertions are newly authored diagnostic probes, never legacy-test results.
Their population and source bytes are frozen before execution. A passing probe
does not establish equivalence. See docs/measurement-spec.md for the separate
original campaign's qualification protocol.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from evaluation.legacy_campaign.execution import invoke
from evaluation.legacy_campaign.protocol import minimal_context
from evaluation.legacy_pilot.assessment import LegacyCase, LegacyTask, sha256, task_mapping
from evaluation.legacy_pilot.run_pilot import (
    classify_build, classify_failure, command_configuration, compose_reactions, runtime_classpath_hashes,
    tree_hashes, write_json,
)
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.workspace import materialize_engine


@dataclass(frozen=True)
class Probe:
    language: str
    task: str
    operators: tuple[str, ...]
    source: str
    test_destination: str
    method: str
    fixture_destination: str = ""
    fixture_source: str = ""
    context_source: str = ""


def is_counterexample(reference: dict[str, Any], mutant: dict[str, Any]) -> bool:
    """Require an observed, reference-passing new behavioral assertion."""
    reference_methods = reference.get("methods", [])
    mutant_methods = mutant.get("methods", [])
    return (reference.get("outcome") == "PASS" and len(reference_methods) == 1
        and reference_methods[0]["outcome"] == "PASS"
        and mutant.get("outcome") == "ASSERTION_FAILURE" and len(mutant_methods) == 1
        and mutant_methods[0]["method"] == reference_methods[0]["method"]
        and "PROBE:" in mutant_methods[0].get("detail", "")
        and reference["job"]["test_sha256"] == mutant["job"]["test_sha256"]
        and reference["job"]["fixture_sha256"] == mutant["job"]["fixture_sha256"]
        and all(reference["job"].get(field) == mutant["job"].get(field)
                for field in ("reference_sha256", "context_sha256"))
        and reference.get("runtime_dependencies") == mutant.get("runtime_dependencies"))


ATL_HELPERS = """
    private java.util.List<EObject> objects(Resource resource, String type) {
        java.util.List<EObject> found = new java.util.ArrayList<>();
        for (java.util.Iterator<EObject> it = resource.getAllContents(); it.hasNext();) {
            EObject obj = it.next();
            if (obj.eClass().getName().equals(type)) found.add(obj);
        }
        return found;
    }
    private Object feature(EObject object, String name) {
        return object.eGet(object.eClass().getEStructuralFeature(name));
    }
"""


def atl_probe(task: LegacyTask, operators: tuple[str, ...], assertions: str,
              fixture: str = "") -> Probe:
    """Copy legacy setup into a separately named diagnostic class, adding checks."""
    source = task.java_file.read_text(encoding="utf-8")
    source = source.replace(task.class_name, "EquivalenceProbeTest")
    lines = source.splitlines(keepends=True)
    injection = next(index for index, line in enumerate(lines) if "Resource outRes = executeAtl(" in line)
    lines.insert(injection + 1, "\n        // Supplementary probe, outside the original legacy suite.\n" + assertions + "\n")
    source = "".join(lines)
    closing = source.rfind("}")
    source = source[:closing] + ATL_HELPERS + source[closing:]
    fixture_path = "src/main/resources/models/cpl_input.xmi" if fixture else ""
    return Probe("atl", task.task, operators, source,
                 "src/test/java/org/example/EquivalenceProbeTest.java", task.cases[0].method,
                 fixture_path, fixture)


def probes() -> tuple[Probe, ...]:
    """Fixed targeted population, selected by source changes before running probes."""
    tasks = {(task.language, task.task): task for task in task_mapping()}
    definitions = [
        ("Grafcet2PetriNet_All", ("M8",), 'assertEquals(3, ((java.util.Collection<?>) feature(objects(outRes, "PetriNet").get(0), "elements")).size(), "PROBE: complete contained elements");'),
        ("PetriNet2Grafcet_All", ("M8",), 'assertEquals(3, ((java.util.Collection<?>) feature(objects(outRes, "Grafcet").get(0), "elements")).size(), "PROBE: complete contained elements");'),
        ("Make2Ant_All", ("M5", "M6"), '''assertEquals(1, objects(outRes, "Echo").size(), "PROBE: displayed shell line creates Echo");
        java.util.List<?> tasksOut = (java.util.List<?>) feature(objects(outRes, "Target").get(0), "tasks");
        assertEquals(java.util.List.of("Echo", "Exec"), tasksOut.stream().map(x -> ((EObject)x).eClass().getName()).collect(java.util.stream.Collectors.toList()), "PROBE: ordered target tasks");'''),
        ("BibTeX2DocBook_All", ("M8",), '''EObject titles = objects(outRes, "Sect1").stream().filter(x -> "Titles List".equals(feature(x, "title"))).findFirst().orElseThrow();
        java.util.List<?> paras = (java.util.List<?>) feature(titles, "paras");
        assertEquals("ATL in Practice", feature((EObject)paras.get(0), "content"), "PROBE: titles sorted by title");'''),
        ("DSL2KM3_All", ("M4", "M6", "M8"), '''assertEquals(6, objects(outRes, "Attribute").size(), "PROBE: attributes reached");
        for (EObject attribute : objects(outRes, "Attribute")) assertEquals(false, feature(attribute, "isOrdered"), "PROBE: attribute ordering flag");
        EObject book = objects(outRes, "Class").stream().filter(x -> "Book".equals(feature(x, "name"))).findFirst().orElseThrow();
        java.util.List<?> features = (java.util.List<?>) feature(book, "structuralFeatures");
        assertEquals(java.util.List.of("title", "isbn", "year", "book"), features.stream().map(x -> feature((EObject)x, "name")).collect(java.util.stream.Collectors.toList()), "PROBE: ordered class features");
        assertEquals(3, ((java.util.Collection<?>) feature(objects(outRes, "Enumeration").get(0), "literals")).size(), "PROBE: enumeration literals");'''),
    ]
    result = [atl_probe(tasks[("atl", task)], operators, assertions) for task, operators, assertions in definitions]
    cpl = '''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:CPL="CPL">
  <CPL:CPL xmi:id="cpl1">
    <incoming xmi:id="inc1">
      <contents xmi:type="CPL:Location" url="sip:probe@example.org" clear="yes">
        <contents xmi:type="CPL:Proxy" timeout="20" recurse="yes" ordering="parallel"><redirection/></contents>
      </contents>
    </incoming>
    <subActions id="helper"><contents xmi:type="CPL:Proxy" timeout="20" recurse="yes" ordering="parallel"/></subActions>
  </CPL:CPL>
</xmi:XMI>
'''
    result.append(atl_probe(tasks[("atl", "CPL2SPL_All")], ("M5", "M6"), '''EObject helper = objects(outRes, "LocalFunctionDeclaration").stream().filter(x -> "helper".equals(feature(x, "name"))).findFirst().orElseThrow();
        assertEquals(1, ((java.util.Collection<?>) feature(helper, "statements")).size(), "PROBE: nonempty subaction statements");
        assertEquals(1, ((java.util.Collection<?>) feature(objects(outRes, "Method").get(0), "statements")).size(), "PROBE: incoming method statements");
        EObject select = objects(outRes, "SelectStat").get(0);
        java.util.Collection<?> cases = (java.util.Collection<?>) feature(select, "selectCases");
        assertTrue(cases.stream().anyMatch(x -> ((java.util.Collection<?>)feature((EObject)x, "commentsBefore")).contains("// redirection")), "PROBE: redirection case attached to select statement");''', cpl))
    qvto_source = '''package org.eclipse.qvto.tests;
import org.junit.jupiter.api.Test;
import org.eclipse.emf.ecore.EClass;
import org.eclipse.emf.ecore.EPackage;
import static org.junit.jupiter.api.Assertions.*;
class EquivalenceProbeTest extends QvtoTestBase {
    @Test void probe() {
        EPackage out = getSingleRootPackage(executeTransformation("MappingBody.qvto", loadInputModel("models/in.ecore")));
        EClass b = assertHasClass(out, "mappedB");
        assertEquals(0, b.getEOperations().size(), "PROBE: constructor must not add an EOperation");
    }
}
'''
    result.append(Probe("qvto", "MappingBody", ("M6",), qvto_source,
        "qvto-tests/actual/src/test/java/org/eclipse/qvto/tests/EquivalenceProbeTest.java", "probe"))
    primary_source = '''package org.eclipse.epsilon.examples.etl.flowchart;
import org.junit.jupiter.api.Test;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import static org.junit.jupiter.api.Assertions.*;
class EquivalenceProbeTest extends FlowchartTestBase {
    @Test void probe() throws Exception {
        EmfModel input = loadWakeupModel(), output = createHtmlModel();
        runEtl("transformations/primary.etl", input, output);
        EObject div = (EObject) output.getAllOfType("DIV").iterator().next();
        java.util.List<?> children = (java.util.List<?>) div.eGet(div.eClass().getEStructuralFeature("children"));
        assertEquals(5, children.size(), "PROBE: five DIV headings");
        for (Object child : children) assertEquals("H1", ((EObject)child).eClass().getName(), "PROBE: primary equivalent selected");
    }
}
'''
    result.append(Probe("etl", "primary", ("M8",), primary_source,
        "src/test/java/org/eclipse/epsilon/examples/etl/flowchart/EquivalenceProbeTest.java", "probe"))
    oo_source = '''package org.eclipse.epsilon.examples.etl;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.eclipse.emf.ecore.EObject;
import org.eclipse.epsilon.emc.emf.EmfModel;
import java.io.File;
import static org.junit.jupiter.api.Assertions.*;
class EquivalenceProbeTest extends EtlTestBase {
    @BeforeEach void setup() throws Exception {
        for (String name : new String[]{"OO", "DB", "TM", "SimpleTrace"}) registerMetamodel("metamodels/" + name + ".ecore");
    }
    @Test void probe() throws Exception {
        EmfModel oo = createEmfModel("OO", "models/OOInstance.model", "OO", true, false);
        EmfModel tm = createEmfModel("OO2DB", "models/OO2DB.model", "TM", true, false);
        EmfModel db = createEmfModelFromFile("DB", File.createTempFile("equivalence-db", ".model").getAbsolutePath(), "DB", false, false);
        EmfModel trace = createEmfModelFromFile("Trace", File.createTempFile("equivalence-trace", ".model").getAbsolutePath(), "SimpleTrace", false, false);
        runEtl("transformations/OO2DB.etl", oo, tm, db, trace);
        EObject table = (EObject) db.getAllOfType("Table").stream().filter(x -> "School_PostCodesAcceptedValues".equals(((EObject)x).eGet(((EObject)x).eClass().getEStructuralFeature("name")))).findFirst().orElseThrow();
        java.util.List<?> columns = (java.util.List<?>) table.eGet(table.eClass().getEStructuralFeature("columns"));
        EObject value = (EObject) columns.stream().filter(x -> "value".equals(((EObject)x).eGet(((EObject)x).eClass().getEStructuralFeature("name")))).findFirst().orElseThrow();
        assertEquals("NVARCHAR", value.eGet(value.eClass().getEStructuralFeature("type")), "PROBE: multi-valued attribute SQL type mapping");
    }
}
'''
    result.append(Probe("etl", "OO2DB", ("M6",), oo_source,
        "src/test/java/org/eclipse/epsilon/examples/etl/EquivalenceProbeTest.java", "probe"))
    return tuple(result)


def reactions_probes() -> tuple[Probe, ...]:
    """Check correspondence state and persistence URI, rather than file existence."""
    roots = (
        ("NetworkToGraph_CreateAndRegisterRoot", "System", "Root", "graph.graph"),
        ("FamiliesToPersons_InsertedFamilyRegister", "FamilyRegister", "PersonRegister", "persons.persons"),
        ("AmaltheaToAscet_ComponentContainerInsertedAsRoot", "ComponentContainer", "AscetModule", "ascet.ascet"),
    )
    mapping = {(task.language, task.task): task for task in task_mapping()}
    result = []
    for name, source_type, target_type, filename in roots:
        task = mapping[("reactions", name)]
        source = task.java_file.read_text(encoding="utf-8").replace(task.class_name, "EquivalenceProbeTest")
        method = task.cases[0].method
        start = source.index("void " + method + "(")
        closing = source.index("\n  }", start)
        addition = f'''
    var sourceRoot = getDefaultView(vsum, List.of({source_type}.class)).getRootObjects({source_type}.class).iterator().next();
    var targetRoot = getDefaultView(vsum, List.of({target_type}.class)).getRootObjects({target_type}.class).iterator().next();
    var nativeSource = vsum.getModelInstance(sourceRoot.eResource().getURI()).getResource().getContents().get(0);
    var nativeTarget = vsum.getModelInstance(targetRoot.eResource().getURI()).getResource().getContents().get(0);
    Assertions.assertTrue(vsum.getCorrespondenceModel().getCorrespondingEObjects(nativeSource).contains(nativeTarget), "PROBE: registered root correspondence");
    Assertions.assertTrue(targetRoot.eResource().getURI().toString().endsWith("/model/{filename}"), "PROBE: target persistence URI");
'''
        source = source[:closing] + addition + source[closing:]
        source = source[:start] + source[start:].replace("    VirtualModel vsum =", "    InternalVirtualModel vsum =", 1)
        context, _ = minimal_context(task)
        result.append(Probe("reactions", name, ("M1", "M4"), source,
            "vsum/src/test/java/tools/vitruv/methodologisttemplate/vsum/EquivalenceProbeTest.java",
            method, context_source=context))
    return tuple(result)


def mixed_roles_probe() -> Probe:
    """Probe ordered structuralFeatures with both Simple/ComplexReference rules."""
    task = next(task for task in task_mapping() if (task.language, task.task) == ("atl", "DSL2KM3_All"))
    fixture = (TARGET.engine_harness("atl") / "src/main/resources/models/dsl_input.xmi").read_text(encoding="utf-8")
    additions = '''    <classifiers xmi:type="DSL:Relationship" xmi:id="complexRel" name="Complex" identity="complex" isAbstract="false" isEmbedding="false" domainModel="dm1">
      <roles xmi:id="complexBook" name="complexBook" identity="complexBook" min="0" max="1" source="cls1" type="cls2" relation="complexRel"/>
      <roles xmi:id="complexAuthor" name="complexAuthor" identity="complexAuthor" min="0" max="1" source="cls2" type="cls1" relation="complexRel"/>
    </classifiers>
'''
    fixture = fixture.replace('    <classifiers xmi:type="DSL:Relationship" xmi:id="rel1"', additions + '    <classifiers xmi:type="DSL:Relationship" xmi:id="rel1"')
    pointing = '''    <classifiers xmi:type="DSL:Relationship" xmi:id="pointsRel" name="Points" identity="points" isAbstract="false" isEmbedding="false" domainModel="dm1">
      <roles xmi:id="points" name="points" identity="points" min="0" max="1" source="cls2" type="complexRel" relation="pointsRel"/>
      <roles xmi:id="pointsBack" name="pointsBack" identity="pointsBack" min="0" max="1" source="complexRel" type="cls2" relation="pointsRel"/>
    </classifiers>
'''
    fixture = fixture.replace('    <types xmi:type="DSL:SimpleType" xmi:id="str1"', pointing + '    <types xmi:type="DSL:SimpleType" xmi:id="str1"')
    assertions = '''EObject book = objects(outRes, "Class").stream().filter(x -> "Book".equals(feature(x, "name"))).findFirst().orElseThrow();
        java.util.List<?> features = (java.util.List<?>) feature(book, "structuralFeatures");
        assertEquals(java.util.List.of("book", "title", "isbn", "year", "complexBook"), features.stream().map(x -> feature((EObject)x, "name")).collect(java.util.stream.Collectors.toList()), "PROBE: mixed rule order of structuralFeatures");'''
    return replace(atl_probe(task, ("M6",), assertions, fixture),
        fixture_destination="src/main/resources/models/dsl_input.xmi")


def software_task_probe() -> Probe:
    """Exercise the software-task branch absent from the original legacy suite."""
    task = next(task for task in task_mapping() if (task.language, task.task) == ("reactions", "AmaltheaToAscet_TaskCreated"))
    source = task.java_file.read_text(encoding="utf-8").replace(task.class_name, "EquivalenceProbeTest")
    start = source.index("  void InterruptTaskCreatedCreatesAscetModule(")
    closing = source.index("\n  }", start)
    method = '''  void softwareTaskContained(@TempDir Path tempDir) {
    TestUserInteraction interaction = new TestUserInteraction();
    interaction.addNextSingleSelection(2);
    InternalVirtualModel vsum = new VirtualModelBuilder()
        .withStorageFolder(tempDir)
        .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(interaction))
        .withChangePropagationSpecifications(new AmaltheaToAscetChangePropagationSpecification())
        .buildAndInitialize();
    vsum.setChangePropagationMode(ChangePropagationMode.TRANSITIVE_CYCLIC);
    addComponentContainer(vsum, tempDir);
    modifyView(getDefaultView(vsum, List.of(ComponentContainer.class)).withChangeDerivingTrait(), (CommittableView v) -> {
      v.getRootObjects(ComponentContainer.class).iterator().next().getTasks().add(AmaltheaFactory.eINSTANCE.createTask());
    });
    var target = getDefaultView(vsum, List.of(AscetModule.class)).getRootObjects(AscetModule.class).iterator().next();
    Assertions.assertEquals(1, target.getTasks().size(), "PROBE: software task added to module");
    Assertions.assertTrue(target.getTasks().get(0) instanceof tools.vitruv.methodologisttemplate.model.ascet.SoftwareTask, "PROBE: software branch selected");'''
    source = source[:start] + method + source[closing:]
    context, _ = minimal_context(task)
    return Probe("reactions", task.task, ("M1",), source,
        "vsum/src/test/java/tools/vitruv/methodologisttemplate/vsum/EquivalenceProbeTest.java",
        "softwareTaskContained", context_source=context)


def empty_elements_probes() -> tuple[Probe, ...]:
    """Check the empty-collection boundary of the two final-model proofs."""
    result = []
    for name, source_type, target_type, fixture_name in (
            ("Grafcet2PetriNet_All", "Grafcet", "PetriNet", "grafcet_input.xmi"),
            ("PetriNet2Grafcet_All", "PetriNet", "Grafcet", "petrinet_input.xmi")):
        task = next(task for task in task_mapping() if (task.language, task.task) == ("atl", name))
        source = task.java_file.read_text(encoding="utf-8").replace(task.class_name, "EquivalenceProbeTest")
        start = source.index("    public void " + task.cases[0].method)
        closing = source.index("\n    }", start)
        execution = source.index("Resource outRes = executeAtl(", start)
        execution_end = source.index("\n", execution)
        assertions = f'''\n        assertEquals(1, objects(outRes, "{target_type}").size(), "PROBE: empty input root mapped");
        assertEquals(0, ((java.util.Collection<?>)feature(objects(outRes, "{target_type}").get(0), "elements")).size(), "PROBE: empty elements boundary");'''
        source = source[:execution_end] + assertions + source[closing:]
        source = source[:source.rfind("}")] + ATL_HELPERS + "}\n"
        fixture = f'''<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0" xmlns:xmi="http://www.omg.org/XMI" xmlns:{source_type}="{source_type}">
  <{source_type}:{source_type} xmi:id="empty" name="Empty" location="line1"/>
</xmi:XMI>
'''
        result.append(Probe("atl", name, ("M8",), source,
            "src/test/java/org/example/EquivalenceProbeTest.java", task.cases[0].method,
            "src/main/resources/models/" + fixture_name, fixture))
    return tuple(result)


def freeze(output: Path, included_tasks: tuple[str, ...] = (), variant: str = "standard") -> dict[str, Any]:
    """Persist all probe bytes and identities before Maven runs; refuse overwrites."""
    output.mkdir(parents=True, exist_ok=False)
    mapping = {(task.language, task.task): task for task in task_mapping()}
    manifest_path = REPO_ROOT / "evaluation/mutants/manifest.json"
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["mutants"]
    catalogue = {(item["language"].lower(), item["task"], item["mutant"]): item
                 for item in entries if item["status"] == "PRESENT"}
    jobs = []
    protected = {str(manifest_path): sha256(manifest_path)}
    variants = {"dsl-mixed-roles": (mixed_roles_probe,), "software-task": (software_task_probe,)}
    if variant == "empty-elements":
        candidates = empty_elements_probes()
    else:
        candidates = tuple(factory() for factory in variants[variant]) if variant in variants else (*probes(), *reactions_probes())
    population = tuple(probe for probe in candidates
        if not included_tasks or f"{probe.language}/{probe.task}" in included_tasks)
    if not population or set(included_tasks) - {f"{probe.language}/{probe.task}" for probe in population}:
        raise ValueError("unknown or empty probe task selection")
    for probe in population:
        task = mapping[(probe.language, probe.task)]
        inputs = output / "inputs" / probe.language / probe.task
        inputs.mkdir(parents=True)
        java = inputs / "EquivalenceProbeTest.java"
        java.write_text(probe.source, encoding="utf-8")
        fixture = None
        if probe.fixture_source:
            fixture = inputs / "fixture.xmi"
            fixture.write_text(probe.fixture_source, encoding="utf-8")
        context = None
        if probe.context_source:
            context = inputs / "context.reactions"
            context.write_text(probe.context_source, encoding="utf-8")
        reference = TARGET.benchmark / "tasks" / probe.language / "references" / (probe.task + "." + probe.language)
        sources = [("reference", reference)] + [(operator, REPO_ROOT / catalogue[(probe.language, probe.task, operator)]["file"]) for operator in probe.operators]
        for role, source in sources:
            digest = sha256(source)
            if role != "reference" and digest != catalogue[(probe.language, probe.task, role)]["mutant_sha256"]:
                raise ValueError(f"mutant hash mismatch: {source}")
            protected[str(source)] = digest
            jobs.append({"job_id": f"{probe.language}--{probe.task}--{role}", "language": probe.language,
                "task": probe.task, "role": role, "source": str(source), "source_sha256": digest,
                "test": str(java), "test_sha256": sha256(java), "test_destination": probe.test_destination,
                "method": probe.method, "destination": task.destination,
                "fixture": str(fixture) if fixture else "", "fixture_sha256": sha256(fixture) if fixture else "",
                "fixture_destination": probe.fixture_destination,
                "context": str(context) if context else "", "context_sha256": sha256(context) if context else "",
                "reference": str(reference), "reference_sha256": sha256(reference)})
    for language in {job["language"] for job in jobs}:
        engine = TARGET.engine_harness(language)
        protected.update({str(engine / path): digest for path, digest in tree_hashes(engine).items()})
    payload = {"schema_version": "supplementary-equivalence-probes-1", "jobs": jobs, "protected": protected,
        "definition": "Reference-passing behavioral assertion failure on executable mutant establishes a counterexample. PASS never establishes equivalence; technical failures never count as semantic kills.",
        "selection": "Previously unwitnessed task-mutant identities selected from changed source constructs. This is retrospective targeted analysis, not the frozen campaign's independent M_Q.",
        "included_tasks": list(included_tasks),
        "variant": variant,
        "dependency_archive": str(TARGET.artifacts / "legacy-suite-evaluation/campaign-20261008-v1/offline-maven-repository.tar.gz")}
    payload["dependency_archive_sha256"] = sha256(Path(payload["dependency_archive"]))
    payload["executor_sha256"] = sha256(Path(__file__))
    payload["helper_sha256"] = {str(path): sha256(path) for path in (
        REPO_ROOT / "evaluation/legacy_campaign/execution.py",
        REPO_ROOT / "evaluation/legacy_campaign/protocol.py",
        REPO_ROOT / "evaluation/legacy_pilot/run_pilot.py",
        REPO_ROOT / "evaluation/legacy_pilot/assessment.py")}
    write_json(output / "freeze.json", payload)
    shutil.copy2(Path(__file__), output / "executor.py")
    return payload


def run_job(job: dict[str, Any], output: Path, repository: Path, timeout: int) -> dict[str, Any]:
    """Replace candidate only in an isolated template with frozen diagnostic inputs."""
    trial = output / "raw" / job["job_id"]
    if (trial / "execution.json").is_file():
        return json.loads((trial / "execution.json").read_text(encoding="utf-8"))
    trial.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="equivalence-probe-") as temporary:
        engine = materialize_engine(TARGET.engine_harness(job["language"]), Path(temporary), "engine")
        composition = None
        for field, destination_field in (("source", "destination"), ("test", "test_destination"), ("fixture", "fixture_destination")):
            if job[field]:
                shutil.copy2(job[field], engine / job[destination_field])
                shutil.copy2(job[field], trial / ("candidate." + job["language"] if field == "source" else Path(job[field]).name))
        if job.get("context"):
            prepared, composition = compose_reactions(Path(job["context"]).read_text(encoding="utf-8"),
                Path(job["reference"]).read_text(encoding="utf-8"), Path(job["source"]).read_text(encoding="utf-8"))
            (engine / job["destination"]).write_text(prepared, encoding="utf-8")
            (trial / "prepared.reactions").write_text(prepared, encoding="utf-8")
            shutil.copy2(job["context"], trial / "context.reactions")
            pom = engine / "consistency/pom.xml"
            tree = ET.parse(pom)
            ns = "{http://maven.apache.org/POM/4.0.0}"
            dependencies = tree.getroot().find(ns + "dependencies")
            for dependency in list(dependencies):
                if dependency.findtext(ns + "artifactId") == "edu.kit.ipd.sdq.metamodels.families":
                    dependencies.remove(dependency)
            ET.register_namespace("", ns[1:-1])
            tree.write(pom, encoding="UTF-8", xml_declaration=True)
        task = next(task for task in task_mapping() if (task.language, task.task) == (job["language"], job["task"]))
        task = replace(task, java_file=Path(job["test"]), cases=(LegacyCase(job["method"], "behavioral"),))
        command, cwd = command_configuration(task, engine, repository)
        observation = invoke(command, cwd, timeout)
        (trial / "stdout.log").write_text(observation.pop("stdout"), encoding="utf-8")
        (trial / "stderr.log").write_text(observation.pop("stderr"), encoding="utf-8")
        logs = (trial / "stdout.log").read_text(encoding="utf-8") + (trial / "stderr.log").read_text(encoding="utf-8")
        methods = []
        reports = sorted(engine.rglob("target/surefire-reports/TEST-*.xml"))
        for report in reports:
            destination = trial / "reports" / report.relative_to(engine)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report, destination)
            for case in ET.parse(report).getroot().iter("testcase"):
                if not case.get("classname", "").endswith(".EquivalenceProbeTest"):
                    continue
                node = case.find("failure")
                kind = "failure"
                if node is None:
                    node, kind = case.find("error"), "error"
                outcome = "PASS" if node is None else classify_failure(kind, node.get("type", ""), node.get("message", ""), node.text or "")
                methods.append({"method": case.get("name"), "outcome": outcome,
                    "detail": "" if node is None else node.get("message", "") + "\n" + (node.text or "")})
        outcome = methods[0]["outcome"] if len(methods) == 1 else classify_build(logs)
        if observation["timed_out"] or len(methods) > 1:
            outcome = "INFRASTRUCTURE_ERROR"
        result = {"job": job, **observation, "command": command, "cwd": str(cwd), "methods": methods,
            "outcome": outcome, "composition": composition,
            "runtime_dependencies": runtime_classpath_hashes(reports, repository)}
        write_json(trial / "execution.json", result)
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--task", action="append", default=[], help="Optional language/task selection; repeatable.")
    parser.add_argument("--variant", choices=("standard", "dsl-mixed-roles", "software-task", "empty-elements"), default="standard")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    output = args.output.resolve()
    population = json.loads((output / "freeze.json").read_text(encoding="utf-8")) if (output / "freeze.json").is_file() else freeze(output, tuple(args.task), args.variant)
    if sha256(Path(__file__)) != population["executor_sha256"]:
        raise ValueError("executor differs from the frozen version")
    for path, digest in population.get("helper_sha256", {}).items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"executor helper changed: {path}")
    for path, digest in population["protected"].items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"protected input changed: {path}")
    results = []
    with tempfile.TemporaryDirectory(prefix="equivalence-dependencies-") as temporary:
        root = Path(temporary)
        archive = Path(population["dependency_archive"])
        if sha256(archive) != population["dependency_archive_sha256"]:
            raise ValueError("dependency archive changed")
        with tarfile.open(archive) as stream:
            stream.extractall(root, filter="data")
        for job in population["jobs"]:
            for field in ("source", "test", "fixture", "context", "reference"):
                if job[field] and sha256(Path(job[field])) != job[field + "_sha256"]:
                    raise ValueError(f"frozen {field} changed: {job['job_id']}")
            result = run_job(job, output, root / "repository", args.timeout)
            results.append(result)
            print(job["job_id"], result["outcome"], flush=True)
    for path, digest in population["protected"].items():
        if sha256(Path(path)) != digest:
            raise ValueError(f"protected input changed during execution: {path}")
    write_json(output / "results.json", results)
    write_json(output / "integrity.json", {"protected_inputs_unchanged": True, "jobs": len(results),
        "raw_hashes": {str(path.relative_to(output / "raw")): sha256(path)
            for path in sorted((output / "raw").rglob("*")) if path.is_file()},
        "freeze_sha256": sha256(output / "freeze.json")})


if __name__ == "__main__":
    main()
