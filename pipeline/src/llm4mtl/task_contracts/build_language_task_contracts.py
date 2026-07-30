"""Build deterministic task contracts for ATL, QVT-O, and Reactions.

Reference transformations declare runtime slots and metamodel aliases. Ecore
files provide namespace and classifier facts. This command joins those two
authoritative inputs; it does not infer behavioural expectations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.conventions import (
    default_references_root,
    default_task_contracts_root,
    language_config,
)
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.task_contracts import contract_from_mapping
from llm4mtl.task_contracts.render import contract_header_markdown

ATL_SIGNATURE = re.compile(
    r"\bcreate\s+(?P<out_name>\w+)\s*:\s*(?P<out_alias>\w+)"
    r"\s+from\s+(?P<in_name>\w+)\s*:\s*(?P<in_alias>\w+)\s*;",
    re.IGNORECASE | re.DOTALL,
)
ATL_TYPE = re.compile(r"\b([A-Za-z_]\w*)!([A-Za-z_]\w*)")
QVTO_MODELTYPES = re.compile(
    r"\bmodeltype\s+(\w+)\s+uses\s+['\"]([^'\"]+)['\"]\s*;",
    re.IGNORECASE,
)
QVTO_SIGNATURE = re.compile(
    r"\btransformation\s+\w+\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
QVTO_PARAMETER = re.compile(r"\b(inout|in|out)\s+(\w+)\s*:\s*(\w+)", re.IGNORECASE)
REACTIONS_IMPORT = re.compile(
    r"\bimport\s+['\"]([^'\"]+)['\"]\s+as\s+(\w+)",
    re.IGNORECASE,
)
REACTIONS_TYPE = re.compile(r"\b([A-Za-z_]\w*)::([A-Za-z_]\w*)")

ECORE_TYPES = (
    "EAnnotation",
    "EAttribute",
    "EClass",
    "EClassifier",
    "EDataType",
    "EEnum",
    "EEnumLiteral",
    "EFactory",
    "EGenericType",
    "EModelElement",
    "ENamedElement",
    "EObject",
    "EOperation",
    "EPackage",
    "EParameter",
    "EReference",
    "EStringToStringMapEntry",
    "EStructuralFeature",
    "ETypedElement",
    "ETypeParameter",
)

ATL_ECORE_OVERRIDES = {
    "ieee1471": "IEEE1471ConceptualModel.ecore",
    "modaf": "MoDAF-AV.ecore",
}


@dataclass(frozen=True)
class EcoreInfo:
    path: Path
    name: str
    ns_uri: str
    ns_prefix: str
    classifiers: tuple[str, ...]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic non-ETL task contracts."
    )
    parser.add_argument(
        "--language",
        choices=("atl", "qvto", "reactions"),
        required=True,
    )
    parser.add_argument("--references-root", type=Path)
    parser.add_argument("--contracts-root", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = language_config(args.language)
    references_root = args.references_root or default_references_root(config)
    contracts_root = args.contracts_root or default_task_contracts_root(config)
    contracts_root.mkdir(parents=True, exist_ok=True)

    builders = {
        "atl": build_atl_contract,
        "qvto": build_qvto_contract,
        "reactions": build_reactions_contract,
    }
    extension = {"atl": ".atl", "qvto": ".qvto", "reactions": ".reactions"}[
        args.language
    ]
    references = sorted(references_root.glob(f"*{extension}"))
    if not references:
        raise RuntimeError(f"no {args.language} references under {references_root}")

    for reference in references:
        contract = builders[args.language](reference)
        task = reference.stem
        (contracts_root / f"{task}.json").write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        typed = contract_from_mapping(contract)
        (contracts_root / f"{task}.txt").write_text(
            contract_header_markdown(typed) + "\n",
            encoding="utf-8",
        )
    return 0


def build_atl_contract(reference: Path) -> dict[str, Any]:
    source = reference.read_text(encoding="utf-8")
    signature = ATL_SIGNATURE.search(source)
    if signature is None:
        raise ValueError(f"cannot read ATL model signature from {reference}")

    used: dict[str, set[str]] = {}
    for alias, type_name in ATL_TYPE.findall(source):
        used.setdefault(alias.lower(), set()).add(type_name)

    models = []
    for role, runtime_group, alias_group in (
        ("source", "in_name", "in_alias"),
        ("target", "out_name", "out_alias"),
    ):
        runtime_name = signature.group(runtime_group)
        alias = signature.group(alias_group)
        ecore = resolve_atl_ecore(alias)
        models.append(
            model_mapping(
                runtime_name,
                (role,),
                alias,
                ecore,
                sorted(used.get(alias.lower(), set())),
            )
        )
    return contract_mapping("atl", reference, models)


def build_qvto_contract(reference: Path) -> dict[str, Any]:
    source = reference.read_text(encoding="utf-8")
    modeltypes = {
        alias: uri
        for alias, uri in QVTO_MODELTYPES.findall(source)
    }
    signature = QVTO_SIGNATURE.search(source)
    if signature is None:
        raise ValueError(f"cannot read QVT-O model signature from {reference}")

    models = []
    for direction, runtime_name, alias in QVTO_PARAMETER.findall(signature.group(1)):
        role = {"in": "source", "out": "target", "inout": "inout"}[
            direction.lower()
        ]
        uri = modeltypes.get(alias)
        if not uri:
            raise ValueError(f"QVT-O alias {alias} has no modeltype in {reference}")
        models.append(
            {
                "runtimeName": runtime_name,
                "roles": [role],
                "kind": "emf",
                "metamodelUri": uri,
                "metamodelNsPrefix": "ecore",
                "metamodelAlias": alias,
                "metamodelFile": None,
                "typesUsedInTransformation": sorted(
                    type_name
                    for type_name in ECORE_TYPES
                    if re.search(rf"\b{re.escape(type_name)}\b", source)
                ),
                "availableTypes": list(ECORE_TYPES),
            }
        )
    return contract_mapping("qvto", reference, models)


def build_reactions_contract(reference: Path) -> dict[str, Any]:
    source = reference.read_text(encoding="utf-8")
    imports = REACTIONS_IMPORT.findall(source)
    if len(imports) < 2:
        raise ValueError(f"cannot read Reactions imports from {reference}")
    used: dict[str, set[str]] = {}
    for alias, type_name in REACTIONS_TYPE.findall(source):
        used.setdefault(alias.lower(), set()).add(type_name)

    models = []
    for uri, alias in imports:
        ecore = resolve_reactions_ecore(alias)
        if ecore.ns_uri != uri:
            raise ValueError(
                f"{reference}: import URI {uri!r} disagrees with {ecore.path} "
                f"({ecore.ns_uri!r})"
            )
        models.append(
            model_mapping(
                alias,
                ("inout",),
                alias,
                ecore,
                sorted(used.get(alias.lower(), set())),
            )
        )
    return contract_mapping("reactions", reference, models)


def contract_mapping(
    language: str,
    reference: Path,
    models: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schemaVersion": "1.0",
        "task": reference.stem,
        "language": language,
        "transformation": reference.name,
        "reference": relative(reference),
        "sourceHash": sha256(reference),
        "models": models,
        "rules": [
            "semantic_cases model slots must map to runtimeName exactly.",
            "EMF namespace URIs and prefixes come only from this contract.",
            "Assertions and declarative changes may use only availableTypes.",
            "The reference transformation remains the behavioural oracle.",
        ],
    }


def model_mapping(
    runtime_name: str,
    roles: tuple[str, ...],
    alias: str,
    ecore: EcoreInfo,
    used_types: list[str],
) -> dict[str, Any]:
    return {
        "runtimeName": runtime_name,
        "roles": list(roles),
        "kind": "emf",
        "metamodelUri": ecore.ns_uri,
        "metamodelNsPrefix": ecore.ns_prefix,
        "metamodelAlias": alias,
        "metamodelFile": relative(ecore.path),
        "typesUsedInTransformation": used_types,
        "availableTypes": list(ecore.classifiers),
    }


def resolve_atl_ecore(alias: str) -> EcoreInfo:
    root = TARGET.benchmark / "metamodels/additional_models/ATL_model"
    override = ATL_ECORE_OVERRIDES.get(alias.lower())
    if override:
        return load_ecore(root / override)
    candidates = [
        path
        for path in root.glob("*.ecore")
        if path.stem.lower() == alias.lower()
    ]
    if len(candidates) != 1:
        raise ValueError(f"cannot resolve ATL alias {alias!r} under {root}")
    return load_ecore(candidates[0])


def resolve_reactions_ecore(alias: str) -> EcoreInfo:
    path = (
        TARGET.benchmark
        / "metamodels/additional_models/Reaction_model"
        / f"{alias.lower()}.ecore"
    )
    if not path.is_file():
        raise ValueError(f"cannot resolve Reactions alias {alias!r}: {path}")
    return load_ecore(path)


def load_ecore(path: Path) -> EcoreInfo:
    package = ET.parse(path).getroot()
    classifiers = tuple(
        str(element.get("name"))
        for element in package.iter()
        if element.tag.endswith("eClassifiers") and element.get("name")
    )
    return EcoreInfo(
        path=path,
        name=str(package.get("name") or path.stem),
        ns_uri=str(package.get("nsURI") or ""),
        ns_prefix=str(package.get("nsPrefix") or ""),
        classifiers=classifiers,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
