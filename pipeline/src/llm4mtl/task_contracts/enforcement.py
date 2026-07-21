"""Enforce a deterministic task contract over a parsed semantic-case spec.

Infrastructure bindings (which metamodels a task uses, their URIs, runtime model
names, ``.ecore`` files, and the XML namespaces of generated input models) are
deterministic facts owned by the contract, not by the LLM. This module rewrites
those bindings from the contract and rejects assertions that reference types the
target metamodels do not define, so mistakes surface as clear contract
violations instead of cryptic Maven/EMF stack traces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from llm4mtl.task_contracts.models import ModelContract, TaskContract


# Namespaces that are part of the XMI serialization itself and must never be
# treated as the model's metamodel namespace.
STANDARD_NS_URIS = {
    "http://www.omg.org/XMI",
    "http://www.w3.org/2001/XMLSchema-instance",
    "http://www.w3.org/2001/XMLSchema",
}

MODEL_FILE_SUFFIXES = (".model", ".xmi", ".xml")


def enforce_contract(
    contract: TaskContract,
    spec: dict[str, Any],
    files: dict[str, str],
) -> list[str]:
    """Rewrite ``spec`` and model ``files`` in place from ``contract``.

    Returns a list of human-readable contract violations. An empty list means
    the suite is consistent with the contract; a non-empty list means the suite
    is invalid and should not be executed.
    """
    violations: list[str] = []
    # Fail-fast: reject metamodels the LLM invented before we overwrite the
    # declared bindings with the contract's own.
    _check_declared_metamodels(contract, spec, violations)

    spec["transformation"] = _transformation_path(contract)
    spec["metamodels"] = contract.emf_metamodel_resources

    for test_index, test in enumerate(spec.get("tests", []), start=1):
        models = test.get("models") or spec.get("models") or []
        assertions = test.get("assertions") or []
        asserted_types = _asserted_types_by_model(assertions)

        model_to_contract: dict[str, ModelContract] = {}
        for model in models:
            matched = _match_model(contract, model, asserted_types, violations, test_index)
            if matched is None:
                continue
            model_to_contract[str(model.get("name"))] = matched
            _apply_binding(model, matched, files)

        _validate_assertion_types(assertions, model_to_contract, violations, test_index)

    return violations


def _check_declared_metamodels(
    contract: TaskContract,
    spec: dict[str, Any],
    violations: list[str],
) -> None:
    known = contract.identifiers
    contract_names = ", ".join(model.runtime_name for model in contract.models)
    for declared in _declared_metamodels(spec):
        if declared.lower() not in known:
            violations.append(
                f"declared metamodel '{declared}' is not part of the "
                f"'{contract.task}' contract (contract models: {contract_names})"
            )


def _declared_metamodels(spec: dict[str, Any]) -> list[str]:
    """Identifiers the LLM used to name metamodels, in stable de-duped order."""
    raw: list[str] = []
    for item in spec.get("metamodels") or []:
        if isinstance(item, dict):
            for key in ("uri", "metamodelUri", "name"):
                if item.get(key):
                    raw.append(str(item[key]))
                    break
        elif isinstance(item, str) and item:
            raw.append(Path(item).stem)
    for test in spec.get("tests", []):
        for model in test.get("models") or []:
            if isinstance(model, dict) and model.get("metamodelUri"):
                raw.append(str(model["metamodelUri"]))

    seen: set[str] = set()
    unique: list[str] = []
    for identifier in raw:
        if identifier and identifier.lower() not in seen:
            seen.add(identifier.lower())
            unique.append(identifier)
    return unique


def _transformation_path(contract: TaskContract) -> str:
    name = Path(contract.transformation).name
    if not name.endswith(".etl"):
        name = f"{name}.etl"
    return f"transformations/{name}"


def _asserted_types_by_model(assertions: list[Any]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for assertion in assertions:
        if not isinstance(assertion, dict):
            continue
        model_name = assertion.get("model")
        type_name = assertion.get("type")
        if model_name and type_name:
            mapping.setdefault(str(model_name), set()).add(str(type_name))
    return mapping


def _match_model(
    contract: TaskContract,
    model: dict[str, Any],
    asserted_types: dict[str, set[str]],
    violations: list[str],
    test_index: int,
) -> ModelContract | None:
    role = model.get("role") or ("source" if model.get("path") else "target")
    candidates = contract.models_for_role(str(role))
    if not candidates:
        violations.append(
            f"test #{test_index}: model '{model.get('name')}' has role '{role}', "
            f"but the '{contract.task}' contract defines no {role} model"
        )
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Multiple models share this role (e.g. OO2DB). Disambiguate deterministically.
    llm_uri = str(model.get("metamodelUri") or "").lower()
    for candidate in candidates:
        if llm_uri and (candidate.metamodel_uri or "").lower() == llm_uri:
            return candidate

    name_key = str(model.get("name") or "").lower()
    for candidate in candidates:
        if name_key and candidate.runtime_name.lower() == name_key:
            return candidate

    wanted = asserted_types.get(str(model.get("name")), set())
    if wanted:
        best = max(candidates, key=lambda candidate: len(wanted & set(candidate.available_types)))
        if wanted & set(best.available_types):
            return best

    violations.append(
        f"test #{test_index}: cannot map {role} model '{model.get('name')}' to a "
        f"unique contract model for '{contract.task}'"
    )
    return None


def _apply_binding(
    model: dict[str, Any],
    contract_model: ModelContract,
    files: dict[str, str],
) -> None:
    old_uri = str(model.get("metamodelUri") or "")
    model["kind"] = contract_model.kind
    model["runtimeName"] = contract_model.runtime_name
    if model.get("path") and _model_file_key(str(model["path"]), files) is not None:
        model["generated"] = True

    if contract_model.kind == "emf" and contract_model.metamodel_uri:
        model["metamodelUri"] = contract_model.metamodel_uri
        if model.get("path"):
            _rewrite_model_namespace(model, old_uri, contract_model.metamodel_uri, files)
    else:
        model.pop("metamodelUri", None)


def _rewrite_model_namespace(
    model: dict[str, Any],
    old_uri: str,
    new_uri: str,
    files: dict[str, str],
) -> None:
    key = _model_file_key(str(model.get("path") or ""), files)
    if key is None:
        return
    updated = _replace_namespace_uri(files[key], old_uri, new_uri)
    if updated != files[key]:
        files[key] = updated


def _model_file_key(path: str, files: dict[str, str]) -> str | None:
    if not path:
        return None
    base = Path(path).name
    for key in files:
        if key.endswith(MODEL_FILE_SUFFIXES) and Path(key).name == base:
            return key
    return None


def _replace_namespace_uri(content: str, old_uri: str, new_uri: str) -> str:
    if not new_uri:
        return content

    # Preferred: rewrite the xmlns whose value equals the URI the LLM guessed.
    if old_uri:
        pattern = re.compile(r'(xmlns:[\w.-]+=")' + re.escape(old_uri) + r'(")')
        rewritten, count = pattern.subn(
            lambda match: match.group(1) + new_uri + match.group(2), content
        )
        if count:
            return rewritten

    # Fallback: if there is exactly one non-standard namespace, rewrite it.
    declarations = re.findall(r'xmlns:([\w.-]+)="([^"]*)"', content)
    custom = [(prefix, uri) for prefix, uri in declarations if uri not in STANDARD_NS_URIS]
    if len(custom) == 1:
        prefix, uri = custom[0]
        return content.replace(
            f'xmlns:{prefix}="{uri}"', f'xmlns:{prefix}="{new_uri}"', 1
        )
    return content


def _validate_assertion_types(
    assertions: list[Any],
    model_to_contract: dict[str, ModelContract],
    violations: list[str],
    test_index: int,
) -> None:
    for assertion_index, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        type_name = assertion.get("type")
        model_name = assertion.get("model")
        if not type_name or not model_name:
            continue
        contract_model = model_to_contract.get(str(model_name))
        if contract_model is None:
            # The model itself failed to map; that violation is already recorded.
            continue
        if contract_model.kind != "emf":
            # plainXml assertions target XML element names, not metamodel types.
            continue
        if str(type_name) not in contract_model.available_types:
            available = ", ".join(contract_model.available_types) or "<none>"
            violations.append(
                f"test #{test_index} assertion #{assertion_index}: type "
                f"'{contract_model.runtime_name}!{type_name}' is not defined in "
                f"metamodel '{contract_model.metamodel_uri}' (available: {available})"
            )
