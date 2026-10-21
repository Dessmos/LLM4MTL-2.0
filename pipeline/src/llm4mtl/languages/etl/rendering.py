"""Deterministic ETL/JUnit renderer for canonical semantic cases."""

from __future__ import annotations

from typing import Any

from llm4mtl.languages.java_resources import java_lines
from llm4mtl.semantic_tests.codegen.java_rendering import (
    assertion_message,
    escape_java,
    java_bool,
    java_string_array,
    java_string_list,
    java_value,
    object_signatures,
    safe_temp_prefix,
    rendered_method_name,
)
from llm4mtl.semantic_tests.semantic_spec import default_transformation, effective_models
from llm4mtl.semantic_tests.suites.generated_models import generated_model_resource


def render_semantic_test(class_name: str, spec: dict[str, Any], task: str) -> str:
    """Render the JUnit class that runs every test case of ``spec`` with ETL."""
    methods = [render_test_method(spec, test, task) for test in spec["tests"]]
    return "\n".join(
        [
            *java_lines(__package__, "header.java.txt"),
            *_render_class_opening(class_name, spec, task),
            *methods,
            *java_helpers(),
            "}",
            "",
        ]
    )


def _render_class_opening(
    class_name: str, spec: dict[str, Any], task: str
) -> list[str]:
    """The class line, the transformation constant, and metamodel setup."""
    transformation = str(spec.get("transformation") or default_transformation(task))
    metamodels = metamodel_paths(spec.get("metamodels", []))
    return [
        f"public class {class_name} extends EtlTestBase {{",
        f'    private static final String ETL = "{escape_java(transformation)}";',
        "",
        "    @BeforeEach",
        "    public void setUpGeneratedMetamodels() throws Exception {",
        *[f'        registerMetamodel("{escape_java(path)}");' for path in metamodels],
        "    }",
        "",
    ]


def render_test_method(spec: dict[str, Any], test: dict[str, Any], task: str) -> str:
    method_name = rendered_method_name(test)
    models = effective_models(spec, test)
    model_vars = {
        str(model["name"]): f"model{index}" for index, model in enumerate(models)
    }
    lines = [
        "    @Test",
        f"    public void {method_name}() throws Exception {{",
        "        List<IModel> generatedModels = new ArrayList<>();",
    ]

    for index, model in enumerate(models):
        lines.extend(render_model_creation(model, f"model{index}", task))
        lines.append(f"        generatedModels.add(model{index});")

    lines.append("        runEtl(ETL, generatedModels.toArray(new IModel[0]));")
    # Write snapshots before the assertions, so the real output survives the
    # first failing assertion. Source Diagnosis needs that output; "expected !=
    # actual" alone does not show a missing edge or a wrong reference.
    lines.extend(_render_snapshot_writes(models, method_name))
    for assertion in test["assertions"]:
        lines.extend(render_assertion(assertion, model_vars))
    lines.extend(["    }", ""])
    return "\n".join(lines)


def _render_snapshot_writes(
    models: list[dict[str, Any]], method_name: str
) -> list[str]:
    """One ``writeSnapshot`` call per EMF target model."""
    lines = []
    for index, model in enumerate(models):
        if model.get("role") != "target" or model.get("kind", "emf") != "emf":
            continue
        snapshot = f"{escape_java(method_name)}/{escape_java(str(model['name']))}.xmi"
        lines.append(f'        writeSnapshot("{snapshot}", model{index});')
    return lines


def render_model_creation(model: dict[str, Any], var_name: str, task: str) -> list[str]:
    kind = model.get("kind", "emf")
    role = model.get("role", "source" if model.get("path") else "target")
    if kind == "plainXml":
        return render_plain_xml_model(model, var_name, role, task)
    return render_emf_model(model, var_name, role, task)


def render_emf_model(
    model: dict[str, Any], var_name: str, role: str, task: str
) -> list[str]:
    name = escape_java(runtime_model_name(model))
    metamodel_uri = escape_java(str(model["metamodelUri"]))
    read_on_load = java_bool(model.get("readOnLoad", role == "source"))
    store_on_disposal = java_bool(model.get("storeOnDisposal", role == "target"))
    flags = f"{read_on_load}, {store_on_disposal}"
    if role == "source":
        path = escape_java(_source_model_path(model, task))
        return [
            f'        EmfModel {var_name} = createEmfModel("{name}", "{path}", '
            f'"{metamodel_uri}", {flags});'
        ]

    extension = str(model.get("fileExtension") or ".model")
    return [
        *_render_temp_file(var_name, name, extension),
        f'        EmfModel {var_name} = createEmfModelFromFile("{name}", '
        f'{var_name}File.getAbsolutePath(), "{metamodel_uri}", {flags});',
    ]


def render_plain_xml_model(
    model: dict[str, Any], var_name: str, role: str, task: str
) -> list[str]:
    name = escape_java(runtime_model_name(model))
    read_on_load = java_bool(model.get("readOnLoad", role == "source"))
    store_on_disposal = java_bool(model.get("storeOnDisposal", role == "target"))
    lines = [
        f"        PlainXmlModel {var_name} = new PlainXmlModel();",
        f'        {var_name}.setName("{name}");',
    ]
    if role == "source":
        path = escape_java(_source_model_path(model, task))
        lines.append(
            f'        {var_name}.setFile(new File(getResourcePath("{path}")));'
        )
    else:
        extension = str(model.get("fileExtension") or ".xml")
        lines.extend(_render_temp_file(var_name, name, extension))
        lines.append(f"        {var_name}.setFile({var_name}File);")
    lines.extend(
        [
            f"        {var_name}.setReadOnLoad({read_on_load});",
            f"        {var_name}.setStoredOnDisposal({store_on_disposal});",
            f"        {var_name}.load();",
        ]
    )
    return lines


def _source_model_path(model: dict[str, Any], task: str) -> str:
    return model_resource_path(
        str(model["path"]), task, bool(model.get("generated", True))
    )


def _render_temp_file(var_name: str, name: str, extension: str) -> list[str]:
    """Declare ``<var_name>File``, an empty temporary file for a target model."""
    prefix = safe_temp_prefix(name)
    return [
        f"        File {var_name}File = "
        f'File.createTempFile("{prefix}_", "{escape_java(extension)}");',
        f"        {var_name}File.deleteOnExit();",
    ]


def runtime_model_name(model: dict[str, Any]) -> str:
    for key in ("runtimeName", "modelName", "alias", "metamodelAlias"):
        if model.get(key):
            return str(model[key])
    if model.get("kind", "emf") == "emf" and model.get("metamodelUri"):
        return str(model["metamodelUri"])
    return str(model["name"])


def render_assertion(
    assertion: dict[str, Any], model_vars: dict[str, str]
) -> list[str]:
    model_var = model_vars[str(assertion["model"])]
    kind = assertion["kind"]
    type_name = escape_java(str(assertion["type"]))
    # The unescaped text is the shared rule; escaping it is this emitter's job.
    message = escape_java(assertion_message(assertion))

    # Raise TypeError for an unhashable (malformed) kind, as callers expect.
    # Validated semantic-case documents always give a string.
    hash(kind)

    match kind:
        case "count":
            return _render_count(assertion, model_var, type_name, message)
        case "featureValues" | "pathValues":
            return _render_path_assertion(assertion, model_var, type_name, message)
        case "treePaths":
            return _render_tree_paths(assertion, model_var, type_name, message)
        case "referencePairs":
            return _render_reference_pairs(assertion, model_var, type_name, message)
        case "collectionSize":
            return _render_collection_size(assertion, model_var, type_name, message)
        case "objects":
            return _render_objects(assertion, model_var, type_name, message)
        case _:
            raise AssertionError(f"Unsupported assertion kind: {kind}")


def _render_count(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    expected = int(assertion["expected"])
    actual = f'allOfType({model_var}, "{type_name}").size()'
    return [f'        assertEquals({expected}, {actual}, "{message}");']


def _render_path_assertion(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    expected = java_string_list([java_value(value) for value in assertion["expected"]])
    path_key = "feature" if assertion["kind"] == "featureValues" else "path"
    path = escape_java(str(assertion[path_key]))
    actual = f'pathValues({model_var}, "{type_name}", "{path}")'
    return render_count_assertion(expected, actual, assertion, message)


def _render_collection_size(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    where = assertion.get("where") if isinstance(assertion.get("where"), dict) else {}
    features = list(where) if where else []
    expected_signature = object_signatures([where], features)[0] if features else ""
    path = escape_java(str(assertion["path"]))
    return [
        f'        assertCollectionSize({model_var}, "{type_name}", '
        f"{java_string_array(features)}, "
        f'"{escape_java(expected_signature)}", "{path}", '
        f'{int(assertion["expected"])}, "{message}");'
    ]


def _render_objects(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    features = [str(feature) for feature in assertion["features"]]
    expected = object_signatures(assertion["expected"], features)
    actual = f'signaturesOf({model_var}, "{type_name}", {java_string_array(features)})'
    return render_count_assertion(
        java_string_list(expected), actual, assertion, message
    )


def _render_tree_paths(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    expected = java_string_list([java_value(value) for value in assertion["expected"]])
    label_feature = escape_java(str(assertion.get("labelFeature") or "label"))
    children_feature = escape_java(str(assertion.get("childrenFeature") or "children"))
    actual = (
        f'treePaths({model_var}, "{type_name}", '
        f'"{label_feature}", "{children_feature}")'
    )
    return render_count_assertion(expected, actual, assertion, message)


def _render_reference_pairs(
    assertion: dict[str, Any], model_var: str, type_name: str, message: str
) -> list[str]:
    expected = [
        f"{java_value(pair['source'])}->{java_value(pair['target'])}"
        for pair in assertion["expected"]
    ]
    source = escape_java(str(assertion["source"]))
    target = escape_java(str(assertion["target"]))
    actual = f'referencePairs({model_var}, "{type_name}", "{source}", "{target}")'
    return render_count_assertion(
        java_string_list(expected), actual, assertion, message
    )


def render_count_assertion(
    expected: str, actual: str, assertion: dict[str, Any], message: str
) -> list[str]:
    if assertion.get("contains") is True:
        return [f'        assertContainsCounts({expected}, {actual}, "{message}");']
    return [f'        assertEquals(counts({expected}), counts({actual}), "{message}");']


def java_helpers() -> list[str]:
    """Java helpers the ETL harness adds to every generated class.

    Notes on the emitted Java:

    * ``writeSnapshot`` copies the target model this run produced out of the
      live EMF resource. A blank observations property means no folder was
      configured; then nothing is written, never a partial file.
    * ``pathValues`` keeps an unset last value as ``"null"``: a suite must be
      able to say that a created element has no name.
    * ``plainXmlFeatureValue`` reads the PlainXml driver's own property names,
      the same names the transformation writes: ``text``, ``a_<attr>``,
      ``e_<tag>`` (first child element), ``c_<tag>`` (all child elements).
    * ``stringValue`` renders values like the shared harness does: an unset
      value reads ``"null"`` and a reference reads its identity.
    """
    return java_lines(__package__, "helpers.java.txt")


def metamodel_paths(raw: Any) -> list[str]:
    paths = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, dict) and item.get("path"):
            paths.append(str(item["path"]))
    return paths


def model_resource_path(path: str, task: str, generated: bool) -> str:
    """The classpath resource of a source model.

    A generated model lives in the suite's own folder on the classpath; any
    other path is already a classpath resource of the harness.
    """
    normalized = path.replace("\\", "/").lstrip("/")
    if not generated:
        return normalized
    return generated_model_resource(task, normalized)
