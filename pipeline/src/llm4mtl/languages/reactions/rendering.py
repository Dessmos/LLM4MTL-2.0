"""Deterministic Reactions/Vitruv JUnit renderer.

The generated Java contains infrastructure only. Changes remain a closed,
declarative vocabulary in ``semantic_cases.json`` and are translated here into
reflective EMF operations; the LLM never supplies executable change code.
"""

from __future__ import annotations

import json
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
from llm4mtl.conventions import REACTIONS_CONFIG, default_task_contracts_root
from llm4mtl.semantic_tests.semantic_spec import effective_models
from llm4mtl.semantic_tests.suites.java import slug

FEATURE_LOOKUP_LINE = (
    "        EStructuralFeature feature = object.eClass().getEStructuralFeature(name);"
)


def prerequisite_tasks(task: str) -> tuple[str, ...]:
    """Tasks whose reactions must run alongside this one, prerequisites first.

    A reaction that retrieves a correspondence cannot act until some other
    task's reaction has established it. Splitting one consistency
    specification into one task per reaction left those tasks unable to do
    anything on their own -- not even the reference transformation -- so the
    contract names what each one presupposes and the chain is walked here.
    """
    root = default_task_contracts_root(REACTIONS_CONFIG)
    ordered: list[str] = []

    def walk(name: str, seen: tuple[str, ...]) -> None:
        if name in seen:
            raise ValueError(f"prerequisite cycle through {name!r}")
        path = root / f"{name}.json"
        if not path.is_file():
            return
        contract = json.loads(path.read_text(encoding="utf-8"))
        for prerequisite in contract.get("prerequisiteTasks") or ():
            walk(str(prerequisite), (*seen, name))
            if prerequisite not in ordered:
                ordered.append(str(prerequisite))

    walk(task, ())
    return tuple(ordered)


def _specification(task: str) -> str:
    return f"{task}ChangePropagationSpecification"


def render_reactions_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    # One specification, always. A virtual model accepts a single change
    # propagation specification per pair of metamodels, and a task's
    # prerequisites work on the very same pair -- they reach the engine merged
    # into this task's reactions file, not as specifications of their own.
    reaction_name = task[:1].lower() + task[1:]
    specification = _specification(task)
    return "\n".join(
        [
            "package tools.vitruv.methodologisttemplate.generated;",
            "",
            *assertion_imports(),
            "import java.net.URL;",
            "import java.nio.file.Path;",
            "import java.util.function.Consumer;",
            "",
            "import org.eclipse.emf.common.util.URI;",
            "import org.eclipse.emf.ecore.EClass;",
            "import org.eclipse.emf.ecore.EDataType;",
            "import org.eclipse.emf.ecore.EFactory;",
            "import org.eclipse.emf.ecore.EPackage;",
            "import org.eclipse.emf.ecore.resource.Resource;",
            "import org.eclipse.emf.ecore.resource.ResourceSet;",
            "import org.eclipse.emf.ecore.resource.impl.ResourceSetImpl;",
            "import org.eclipse.emf.ecore.util.EcoreUtil;",
            "import org.eclipse.emf.ecore.xmi.impl.XMIResourceFactoryImpl;",
            "import org.junit.jupiter.api.BeforeAll;",
            "import org.junit.jupiter.api.Test;",
            "import org.junit.jupiter.api.io.TempDir;",
            "import tools.vitruv.change.propagation.ChangePropagationSpecification;",
            "import tools.vitruv.change.propagation.ChangePropagationMode;",
            "import tools.vitruv.change.testutils.TestUserInteraction;",
            "import tools.vitruv.framework.views.CommittableView;",
            "import tools.vitruv.framework.views.View;",
            "import tools.vitruv.framework.views.ViewTypeFactory;",
            "import tools.vitruv.framework.vsum.VirtualModelBuilder;",
            "import tools.vitruv.framework.vsum.internal.InternalVirtualModel;",
            f"import mir.reactions.{reaction_name}.{specification};",
            "",
            f"public class {class_name} {{",
            "    @BeforeAll",
            "    static void registerFactories() {",
            '        Resource.Factory.Registry.INSTANCE.getExtensionToFactoryMap().put("*", new XMIResourceFactoryImpl());',
            "    }",
            "",
            *[
                _render_method(test, task, specification)
                for test in spec["tests"]
            ],
            *_reactions_helpers(),
            *assertion_helpers(),
            "}",
            "",
        ]
    )


def _render_method(
    test: dict[str, Any],
    task: str,
    specification: str,
) -> str:
    models = effective_models({}, test)
    slot_uris = {
        str(model["name"]): str(model["metamodelUri"])
        for model in models
    }
    lines = [
        "    @Test",
        f"    void {sanitize_method_name(str(test['name']))}(@TempDir Path tempDir) throws Exception {{",
        f"        InternalVirtualModel vsum = createVirtualModel(tempDir, new {specification}());",
    ]
    for model in models:
        path = model.get("path")
        if not path:
            continue
        relative = str(path).replace("\\", "/")
        if relative.startswith("models/"):
            relative = relative[len("models/") :]
        resource = f"generated-models/{slug(task)}/{relative}"
        lines.append(
            f'        registerInitialModel(vsum, tempDir, "{escape_java(resource)}");'
        )

    for index, change in enumerate(test.get("changes", [])):
        lines.extend(_render_change(change, slot_uris, index))

    variables: dict[str, str] = {}
    for index, model in enumerate(models):
        variable = f"model{index}Roots"
        variables[str(model["name"])] = variable
        lines.append(
            f'        List<EObject> {variable} = modelRoots(vsum, "{escape_java(str(model["metamodelUri"]))}");'
        )
        lines.append(
            f'        writeSnapshot("{escape_java(sanitize_method_name(str(test["name"])))}/{escape_java(str(model["name"]))}.xmi", {variable});'
        )
    lines.extend(render_assertions(test["assertions"], variables))
    lines.extend(["    }", ""])
    return "\n".join(lines)


def _render_change(
    change: dict[str, Any],
    slot_uris: dict[str, str],
    index: int,
) -> list[str]:
    target = change["target"]
    slot = str(target.get("slot", target.get("model")))
    uri = slot_uris[slot]
    kind = str(change["kind"])
    feature = escape_java(str(change.get("feature") or ""))
    value = change.get("value")
    if kind == "create":
        body = [
            f"            EObject created{index} = {_java_value(value, slot_uris, 'view', uri)};",
        ]
        if feature:
            target_expression = _find_expression("view", uri, target)
            body.append(
                f'            addToCollection({target_expression}, "{feature}", created{index});'
            )
        else:
            body.append(
                f"            view.registerRoot(created{index}, "
                "URI.createFileURI(tempDir.resolve("
                f'"created-{index}.xmi").toString()));'
            )
    elif kind == "delete":
        target_expression = _find_expression("view", uri, target)
        body = [f"            EcoreUtil.delete({target_expression}, true);"]
    else:
        operation = {
            "set_feature": "setFeature",
            "add_to_collection": "addToCollection",
            "remove_from_collection": "removeFromCollection",
            "move": "moveInto",
        }.get(kind)
        if operation is None:
            raise ValueError(f"unsupported Reactions change kind: {kind}")
        target_expression = _find_expression("view", uri, target)
        rendered_value = _java_value(value, slot_uris, "view", uri)
        body = [
            f'            {operation}({target_expression}, "{feature}", {rendered_value});'
        ]
    return [
        "        modify(vsum, view -> {",
        *body,
        "        });",
    ]


def _java_value(
    value: Any,
    slot_uris: dict[str, str],
    view: str,
    default_uri: str,
) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Boolean.TRUE" if value else "Boolean.FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return f'"{escape_java(value)}"'
    if not isinstance(value, dict):
        raise ValueError(f"unsupported declarative change value: {value!r}")
    return _java_object_value(value, slot_uris, view, default_uri)


def _java_object_value(
    value: dict[str, Any],
    slot_uris: dict[str, str],
    view: str,
    default_uri: str,
) -> str:
    if value.get("slot") or value.get("model"):
        slot = str(value.get("slot", value.get("model")))
        return _find_expression(view, slot_uris[slot], value)
    type_name = value.get("type")
    if not type_name:
        raise ValueError("a created element needs a type")
    features = value.get("features") if isinstance(value.get("features"), dict) else {}
    return (
        f'createObject("{escape_java(default_uri)}", "{escape_java(str(type_name))}", '
        f"{_java_map(features)})"
    )


def _find_expression(view: str, uri: str, reference: dict[str, Any]) -> str:
    return (
        f'find({view}, "{escape_java(uri)}", "{escape_java(str(reference["type"]))}", '
        f'{_java_map(reference.get("where") if isinstance(reference.get("where"), dict) else {})})'
    )


def _java_map(values: dict[str, Any]) -> str:
    if not values:
        return "map()"
    entries: list[str] = []
    for key, value in values.items():
        entries.append(f'"{escape_java(str(key))}"')
        entries.append(_java_literal(value))
    return f"map({', '.join(entries)})"


def _java_literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "Boolean.TRUE" if value else "Boolean.FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{escape_java(str(value))}"'


def _reactions_helpers() -> list[str]:
    return [
        "    private Map<String, Object> map(Object... entries) {",
        "        if (entries.length % 2 != 0) throw new IllegalArgumentException(\"map needs key/value pairs\");",
        "        Map<String, Object> values = new LinkedHashMap<>();",
        "        for (int index = 0; index < entries.length; index += 2) values.put((String) entries[index], entries[index + 1]);",
        "        return values;",
        "    }",
        "",
        "    private InternalVirtualModel createVirtualModel(Path directory, ChangePropagationSpecification specification) {",
        "        InternalVirtualModel model = new VirtualModelBuilder()",
        "            .withStorageFolder(directory)",
        "            .withUserInteractorForResultProvider(new TestUserInteraction.ResultProvider(new TestUserInteraction()))",
        "            .withChangePropagationSpecifications(specification)",
        "            .buildAndInitialize();",
        "        model.setChangePropagationMode(ChangePropagationMode.TRANSITIVE_CYCLIC);",
        "        return model;",
        "    }",
        "",
        "    private View allView(InternalVirtualModel vsum) {",
        "        var selector = vsum.createSelector(ViewTypeFactory.createIdentityMappingViewType(\"llm4mtl\"));",
        "        selector.getSelectableElements().forEach(element -> selector.setSelected(element, true));",
        "        return selector.createView();",
        "    }",
        "",
        "    private void registerInitialModel(InternalVirtualModel vsum, Path directory, String resourcePath) throws Exception {",
        "        URL url = getClass().getClassLoader().getResource(resourcePath);",
        "        if (url == null) throw new IllegalArgumentException(\"Resource not found: \" + resourcePath);",
        "        ResourceSet resourceSet = new ResourceSetImpl();",
        "        Resource resource = resourceSet.getResource(org.eclipse.emf.common.util.URI.createURI(url.toString()), true);",
        "        for (EObject root : new ArrayList<>(resource.getContents())) {",
        "            CommittableView view = allView(vsum).withChangeDerivingTrait();",
        "            view.registerRoot(root, URI.createFileURI(directory.resolve(resourcePath.replace('/', '_')).toString()));",
        "            view.commitChanges();",
        "        }",
        "    }",
        "",
        "    private void modify(InternalVirtualModel vsum, Consumer<CommittableView> operation) {",
        "        CommittableView view = allView(vsum).withChangeDerivingTrait();",
        "        operation.accept(view);",
        "        view.commitChanges();",
        "    }",
        "",
        "    private List<EObject> modelRoots(InternalVirtualModel vsum, String nsUri) {",
        "        List<EObject> roots = new ArrayList<>();",
        "        for (EObject root : allView(vsum).getRootObjects()) {",
        "            if (root.eClass().getEPackage().getNsURI().equals(nsUri)) roots.add(root);",
        "        }",
        "        return roots;",
        "    }",
        "",
        "    private EObject find(View view, String nsUri, String type, Map<String, Object> where) {",
        "        List<EObject> roots = new ArrayList<>();",
        "        for (EObject root : view.getRootObjects()) {",
        "            if (root.eClass().getEPackage().getNsURI().equals(nsUri)) roots.add(root);",
        "        }",
        "        for (EObject candidate : allOfType(roots, type)) {",
        "            boolean matches = true;",
        "            for (Map.Entry<String, Object> entry : where.entrySet()) {",
        "                if (!java.util.Objects.equals(String.valueOf(entry.getValue()), stringValue(pathValue(candidate, entry.getKey())))) matches = false;",
        "            }",
        "            if (matches) return candidate;",
        "        }",
        "        throw new IllegalArgumentException(\"Element not found: \" + nsUri + \"::\" + type + \" \" + where);",
        "    }",
        "",
        "    private EObject createObject(String nsUri, String type, Map<String, Object> features) {",
        "        EPackage ePackage = EPackage.Registry.INSTANCE.getEPackage(nsUri);",
        "        if (ePackage == null) throw new IllegalArgumentException(\"Metamodel not registered: \" + nsUri);",
        "        EClass eClass = (EClass) ePackage.getEClassifier(type);",
        "        if (eClass == null) throw new IllegalArgumentException(\"Type not found: \" + nsUri + \"::\" + type);",
        "        EObject object = ePackage.getEFactoryInstance().create(eClass);",
        "        for (Map.Entry<String, Object> entry : features.entrySet()) setFeature(object, entry.getKey(), entry.getValue());",
        "        return object;",
        "    }",
        "",
        "    private void setFeature(EObject object, String name, Object value) {",
        FEATURE_LOOKUP_LINE,
        "        if (feature == null) throw new IllegalArgumentException(\"Feature not found: \" + object.eClass().getName() + \".\" + name);",
        "        object.eSet(feature, coerce(feature, value));",
        "    }",
        "",
        "    @SuppressWarnings(\"unchecked\")",
        "    private void addToCollection(EObject object, String name, Object value) {",
        FEATURE_LOOKUP_LINE,
        "        ((Collection<Object>) object.eGet(feature)).add(coerce(feature, value));",
        "    }",
        "",
        "    @SuppressWarnings(\"unchecked\")",
        "    private void removeFromCollection(EObject object, String name, Object value) {",
        FEATURE_LOOKUP_LINE,
        "        ((Collection<Object>) object.eGet(feature)).remove(coerce(feature, value));",
        "    }",
        "",
        "    private void moveInto(EObject destination, String name, Object value) {",
        "        if (!(value instanceof EObject)) throw new IllegalArgumentException(\"move needs an EObject value\");",
        "        EcoreUtil.remove((EObject) value);",
        "        addToCollection(destination, name, value);",
        "    }",
        "",
        "    private Object coerce(EStructuralFeature feature, Object value) {",
        "        if (!(value instanceof String) || !(feature.getEType() instanceof EDataType)) return value;",
        "        EDataType type = (EDataType) feature.getEType();",
        "        EFactory factory = type.getEPackage().getEFactoryInstance();",
        "        return factory.createFromString(type, (String) value);",
        "    }",
        "",
    ]
