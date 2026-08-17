"""Deterministic ATL/JUnit renderer for canonical semantic cases."""

from __future__ import annotations

from typing import Any

from llm4mtl.languages.java_assertions import (
    helpers as assertion_helpers,
    imports as assertion_imports,
    render_assertions,
)
from llm4mtl.semantic_tests.codegen.java_rendering import (
    escape_java,
    sanitize_method_name,
)
from llm4mtl.semantic_tests.semantic_spec import effective_models
from llm4mtl.semantic_tests.suites.java import slug


def render_atl_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    methods = [
        _render_method(spec, test, task)
        for test in spec["tests"]
    ]
    return "\n".join(
        [
            "package org.example.generated;",
            "",
            *assertion_imports(),
            "import java.io.File;",
            "import java.io.FileReader;",
            "import java.io.Reader;",
            "import java.net.URL;",
            "import java.nio.file.Files;",
            "import java.util.HashMap;",
            "",
            "import org.eclipse.emf.common.util.URI;",
            "import org.eclipse.emf.ecore.EPackage;",
            "import org.eclipse.emf.ecore.resource.Resource;",
            "import org.eclipse.emf.ecore.resource.ResourceSet;",
            "import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;",
            "import org.eclipse.emf.ecore.xmi.impl.EcoreResourceFactoryImpl;",
            "import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;",
            "import org.eclipse.m2m.atl.core.IExtractor;",
            "import org.eclipse.m2m.atl.core.IInjector;",
            "import org.eclipse.m2m.atl.core.IModel;",
            "import org.eclipse.m2m.atl.core.IReferenceModel;",
            "import org.eclipse.m2m.atl.core.ModelFactory;",
            "import org.eclipse.m2m.atl.core.emf.EMFExtractor;",
            "import org.eclipse.m2m.atl.core.emf.EMFInjector;",
            "import org.eclipse.m2m.atl.core.emf.EMFModelFactory;",
            "import org.eclipse.m2m.atl.engine.compiler.atl2006.Atl2006Compiler;",
            "import org.eclipse.m2m.atl.engine.emfvm.launch.EMFVMLauncher;",
            "import org.junit.jupiter.api.BeforeAll;",
            "import org.junit.jupiter.api.Test;",
            "",
            f"public class {class_name} {{",
            "    @BeforeAll",
            "    static void registerFactories() {",
            '        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("xmi", new XMIResourceFactoryImpl());',
            '        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("model", new XMIResourceFactoryImpl());',
            '        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("ecore", new EcoreResourceFactoryImpl());',
            "    }",
            "",
            *methods,
            *_atl_helpers(),
            *assertion_helpers(),
            "}",
            "",
        ]
    )


def _render_method(
    spec: dict[str, Any],
    test: dict[str, Any],
    task: str,
) -> str:
    models = effective_models(spec, test)
    sources = [model for model in models if model.get("role") == "source"]
    targets = [model for model in models if model.get("role") == "target"]
    if len(sources) != 1 or len(targets) != 1:
        raise ValueError(
            f"ATL scenario {test.get('name')!r} needs exactly one source and target model"
        )
    source, target = sources[0], targets[0]
    source_path = _generated_model_path(task, str(source["path"]))
    source_metamodel = _metamodel_name(source)
    target_metamodel = _metamodel_name(target)
    transformation = str(spec["transformation"]).split("/")[-1]
    method_name = sanitize_method_name(str(test["name"]))
    model_variables = {
        str(source["name"]): "sourceRoots",
        str(target["name"]): "targetRoots",
    }
    return "\n".join(
        [
            "    @Test",
            f"    void {method_name}() throws Exception {{",
            f'        Resource source = loadModel("{escape_java(source_path)}", "{escape_java(source_metamodel)}");',
            "        List<EObject> sourceRoots = new ArrayList<>(source.getContents());",
            f'        List<EObject> targetRoots = executeAtl("{escape_java(transformation)}", source, '
            f'"{escape_java(source_metamodel)}", "{escape_java(target_metamodel)}", '
            f'"{escape_java(_metamodel_alias(source))}", "{escape_java(_metamodel_alias(target))}");',
            f'        writeSnapshot("{escape_java(method_name)}/{escape_java(str(target["name"]))}.xmi", targetRoots);',
            *render_assertions(test["assertions"], model_variables),
            "    }",
            "",
        ]
    )


def _runtime_name(model: dict[str, Any]) -> str:
    return str(model.get("runtimeName") or model["name"])


def _metamodel_alias(model: dict[str, Any]) -> str:
    return str(
        model.get("metamodelAlias")
        or model.get("metamodelNsPrefix")
        or _runtime_name(model)
    )


def _metamodel_name(model: dict[str, Any]) -> str:
    path = model.get("metamodelFile")
    if not path:
        raise ValueError(f"ATL model {model.get('name')} has no deterministic metamodel file")
    return str(path).replace("\\", "/").split("/")[-1]


def _generated_model_path(task: str, path: str) -> str:
    relative = path.replace("\\", "/")
    if relative.startswith("models/"):
        relative = relative[len("models/") :]
    return f"generated-models/{slug(task)}/{relative}"


def _atl_helpers() -> list[str]:
    return [
        "    private Resource loadModel(String resourcePath, String ecoreName) throws Exception {",
        "        ResourceSet resourceSet = new ResourceSetImpl();",
        "        EPackage metamodel = loadMetamodel(resourceSet, ecoreName);",
        "        resourceSet.getPackageRegistry().put(metamodel.getNsURI(), metamodel);",
        "        URL url = getClass().getClassLoader().getResource(resourcePath);",
        "        if (url == null) throw new IllegalArgumentException(\"Resource not found: \" + resourcePath);",
        "        return resourceSet.getResource(URI.createURI(url.toString()), true);",
        "    }",
        "",
        "    private EPackage loadMetamodel(ResourceSet resourceSet, String name) {",
        "        URL url = getClass().getClassLoader().getResource(\"metamodels/\" + name);",
        "        if (url == null) throw new IllegalArgumentException(\"Resource not found: metamodels/\" + name);",
        "        Resource resource = resourceSet.getResource(URI.createURI(url.toString()), true);",
        "        return (EPackage) resource.getContents().get(0);",
        "    }",
        "",
        "    private File compileAtl(String transformation) throws Exception {",
        "        File source = new File(\"src/main/atl\", transformation);",
        "        if (!source.isFile()) throw new IllegalArgumentException(\"Transformation not found: \" + source);",
        "        File asm = Files.createTempFile(\"llm4mtl-atl\", \".asm\").toFile();",
        "        asm.deleteOnExit();",
        "        try (Reader reader = new FileReader(source)) {",
        "            new Atl2006Compiler().compile(reader, asm.getAbsolutePath());",
        "        }",
        "        if (asm.length() == 0) throw new IllegalStateException(\"ATL parse errors: empty compiled module\");",
        "        return asm;",
        "    }",
        "",
        "    private List<EObject> executeAtl(String transformation, Resource sourceResource, String sourceEcore, String targetEcore, String sourceAlias, String targetAlias) throws Exception {",
        "        ModelFactory factory = new EMFModelFactory();",
        "        IInjector injector = new EMFInjector();",
        "        IReferenceModel sourceMetamodel = factory.newReferenceModel();",
        "        IReferenceModel targetMetamodel = factory.newReferenceModel();",
        "        URL sourceMm = getClass().getClassLoader().getResource(\"metamodels/\" + sourceEcore);",
        "        URL targetMm = getClass().getClassLoader().getResource(\"metamodels/\" + targetEcore);",
        "        if (sourceMm == null || targetMm == null) throw new IllegalArgumentException(\"Resource not found: ATL metamodel\");",
        "        injector.inject(sourceMetamodel, sourceMm.toString());",
        "        injector.inject(targetMetamodel, targetMm.toString());",
        "        IModel source = factory.newModel(sourceMetamodel);",
        "        injector.inject(source, sourceResource.getURI().toString());",
        "        IModel target = factory.newModel(targetMetamodel);",
        "        EMFVMLauncher launcher = new EMFVMLauncher();",
        "        launcher.initialize(null);",
        "        launcher.addInModel(source, \"IN\", sourceAlias);",
        "        launcher.addOutModel(target, \"OUT\", targetAlias);",
        "        try (java.io.InputStream stream = new java.io.FileInputStream(compileAtl(transformation))) {",
        "            launcher.launch(\"run\", null, new HashMap<>(), stream);",
        "        }",
        "        File output = Files.createTempFile(\"llm4mtl-atl-output\", \".xmi\").toFile();",
        "        output.deleteOnExit();",
        "        IExtractor extractor = new EMFExtractor();",
        "        extractor.extract(target, URI.createFileURI(output.getAbsolutePath()).toString());",
        "        ResourceSet resourceSet = new ResourceSetImpl();",
        "        EPackage targetPackage = loadMetamodel(resourceSet, targetEcore);",
        "        resourceSet.getPackageRegistry().put(targetPackage.getNsURI(), targetPackage);",
        "        Resource resource = resourceSet.getResource(URI.createFileURI(output.getAbsolutePath()), true);",
        "        return new ArrayList<>(resource.getContents());",
        "    }",
        "",
    ]
