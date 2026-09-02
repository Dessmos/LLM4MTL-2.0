"""Build deterministic task contracts for every supported language.

Reference transformations declare runtime slots and metamodel aliases. Ecore
files provide namespace and classifier facts. This command joins those two
authoritative inputs; it does not infer behavioural expectations.

One builder covers all four languages on purpose. ETL used to have its own
command emitting an older contract shape (no ``schemaVersion``/``language``/
``sourceHash``, and ``typesUsedInEtL`` instead of ``typesUsedInTransformation``),
which meant ETL contracts silently skipped the identity and staleness checks
every other language got. Language-specific knowledge is confined to the
``build_*_contract`` functions below; everything downstream sees one shape.
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
ETL_TYPE = re.compile(r"\b([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")
ETL_TRANSFORM = re.compile(
    r"\btransform\b[^:\n]*:\s*([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?"
)
ETL_TO = re.compile(r"\bto\b(?P<body>.*?)(?:\{|\n[^\S\r\n]*\r?\n)", re.DOTALL)
ETL_DECLARED_TYPE = re.compile(r":\s*([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")
ECORE_GLOB = "*.ecore"
ETL_NEW = re.compile(r"\bnew\s+([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")

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
        description="Build deterministic task contracts for one language."
    )
    parser.add_argument(
        "--language",
        choices=tuple(BUILDERS),
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

    references = sorted(references_root.glob(f"*{REFERENCE_EXTENSIONS[args.language]}"))
    if not references:
        raise RuntimeError(f"no {args.language} references under {references_root}")

    for reference in references:
        contract = BUILDERS[args.language](reference)
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
    modeltypes = {alias: uri for alias, uri in QVTO_MODELTYPES.findall(source)}
    signature = QVTO_SIGNATURE.search(source)
    if signature is None:
        raise ValueError(f"cannot read QVT-O model signature from {reference}")

    models = []
    for direction, runtime_name, alias in QVTO_PARAMETER.findall(signature.group(1)):
        role = {"in": "source", "out": "target", "inout": "inout"}[direction.lower()]
        uri = modeltypes.get(alias)
        if not uri:
            raise ValueError(f"QVT-O alias {alias} has no modeltype in {reference}")
        ecore = resolve_qvto_ecore(uri)
        models.append(
            model_mapping(
                runtime_name,
                (role,),
                alias,
                ecore,
                sorted(
                    type_name
                    for type_name in ecore.classifiers
                    if re.search(rf"\b{re.escape(type_name)}\b", source)
                ),
            )
        )
    return contract_mapping("qvto", reference, models)


def build_etl_contract(reference: Path) -> dict[str, Any]:
    """Join ETL's ``Prefix!Type`` usage with the Ecore files under ETL_model.

    ETL names a metamodel by the runtime prefix it binds, so that prefix is both
    the runtime model name and the metamodel alias. A prefix that resolves to no
    Ecore file is a plain-XML slot (rss2atom), which the contract records rather
    than guessing a metamodel for.
    """
    source = reference.read_text(encoding="utf-8")
    used: dict[str, set[str]] = {}
    for prefix, type_name in ETL_TYPE.findall(source):
        used.setdefault(prefix, set()).add(type_name)
    roles = _etl_roles(source)
    ecores = _etl_ecores()

    models = []
    for prefix in sorted(used):
        used_types = sorted(used[prefix])
        ecore = _resolve_etl_ecore(prefix, used_types, ecores)
        slot_roles = tuple(sorted(roles.get(prefix) or {"source"}))
        if ecore is None:
            models.append(
                {
                    "runtimeName": prefix,
                    "roles": list(slot_roles),
                    "kind": "plainXml",
                    "metamodelUri": None,
                    "metamodelNsPrefix": None,
                    "metamodelAlias": prefix,
                    "metamodelFile": None,
                    "typesUsedInTransformation": used_types,
                    "availableTypes": used_types,
                }
            )
            continue
        models.append(model_mapping(prefix, slot_roles, prefix, ecore, used_types))
    return contract_mapping("etl", reference, models)


def _etl_roles(source: str) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    for prefix, _ in ETL_TRANSFORM.findall(source):
        roles.setdefault(prefix, set()).add("source")
    for produced in ETL_TO.finditer(source):
        for prefix, _ in ETL_DECLARED_TYPE.findall(produced.group("body")):
            roles.setdefault(prefix, set()).add("target")
    for prefix, _ in ETL_NEW.findall(source):
        roles.setdefault(prefix, set()).add("target")
    return roles


def _etl_ecores() -> list[EcoreInfo]:
    root = TARGET.benchmark / "metamodels/additional_models/ETL_model"
    return [load_ecore(path) for path in sorted(root.glob(ECORE_GLOB))]


def _resolve_etl_ecore(
    prefix: str,
    used_types: list[str],
    ecores: list[EcoreInfo],
) -> EcoreInfo | None:
    """Prefer the metamodel the prefix names; otherwise the one that fits.

    OO2DB binds the prefix ``OO2DB`` to the TM metamodel, so a name match alone
    is not enough: the narrowest metamodel declaring every used type wins.
    """
    for ecore in ecores:
        if prefix in {ecore.ns_uri, ecore.ns_prefix, ecore.name}:
            return ecore
    fitting = [
        ecore
        for ecore in ecores
        if all(type_name in ecore.classifiers for type_name in used_types)
    ]
    if not fitting:
        return None
    return sorted(fitting, key=lambda item: (len(item.classifiers), item.path.name))[0]


# Which task's reactions have to have run before this task's reaction has a
# correspondence to retrieve. Read off the `retrieve ... corresponding to`
# statements in the references: the task that establishes the correspondence is
# the prerequisite. Direct prerequisites only; the chain is walked where it is
# used. A task that only requires the absence of a correspondence has none.
REACTIONS_PREREQUISITES = {
    "AmaltheaToAscet_TaskCreated": ["AmaltheaToAscet_ComponentContainerInsertedAsRoot"],
    "AmaltheaToAscet_TaskDeleted": ["AmaltheaToAscet_TaskCreated"],
    "FamiliesToPersons_CreatedFather": ["FamiliesToPersons_InsertedFamilyRegister"],
    "FamiliesToPersons_InsertedDaughter": ["FamiliesToPersons_InsertedFamilyRegister"],
    "FamiliesToPersons_DeletedMember": ["FamiliesToPersons_InsertedDaughter"],
    "FamiliesToPersons_DeletedFamily": ["FamiliesToPersons_InsertedDaughter"],
    "NetworkToGraph_ComponentInsertedIntoSystem": [
        "NetworkToGraph_CreateAndRegisterRoot"
    ],
    "NetworkToGraph_ComponentRenamed": ["NetworkToGraph_ComponentInsertedIntoSystem"],
    "NetworkToGraph_ComponentDeleted": ["NetworkToGraph_ComponentInsertedIntoSystem"],
}


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
    contract = contract_mapping("reactions", reference, models)
    prerequisites = REACTIONS_PREREQUISITES.get(reference.stem)
    if prerequisites:
        rules = contract.pop("rules")
        contract["prerequisiteTasks"] = list(prerequisites)
        contract["rules"] = rules
    return contract


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
            "For plainXml slots, use kind='plainXml' and omit metamodelUri.",
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
        return load_ecore(root / override, preferred_package=alias)
    candidates = [
        path for path in root.glob(ECORE_GLOB) if path.stem.lower() == alias.lower()
    ]
    if len(candidates) != 1:
        raise ValueError(f"cannot resolve ATL alias {alias!r} under {root}")
    return load_ecore(candidates[0], preferred_package=alias)


def resolve_qvto_ecore(uri: str) -> EcoreInfo:
    """The Ecore file whose nsURI the ``modeltype`` declaration names.

    QVT-O names its metamodel by URI rather than by file, so resolution goes
    through nsURI. Every QVT-O task in the benchmark declares the Ecore
    metamodel itself; supplying that file is what lets the QVT-O prompt carry
    the same metamodel facts every other language's prompt carries.
    """
    root = TARGET.benchmark / "metamodels/additional_models/QVT-O_model"
    candidates = [
        ecore
        for ecore in (load_ecore(path) for path in sorted(root.glob(ECORE_GLOB)))
        if ecore.ns_uri == uri
    ]
    if len(candidates) != 1:
        raise ValueError(
            f"cannot resolve QVT-O metamodel {uri!r} under {root}: "
            f"{len(candidates)} candidates"
        )
    return candidates[0]


def resolve_reactions_ecore(alias: str) -> EcoreInfo:
    path = (
        TARGET.benchmark
        / "metamodels/additional_models/Reaction_model"
        / f"{alias.lower()}.ecore"
    )
    if not path.is_file():
        raise ValueError(f"cannot resolve Reactions alias {alias!r}: {path}")
    return load_ecore(path)


def load_ecore(path: Path, preferred_package: str | None = None) -> EcoreInfo:
    """Namespace and classifier facts for one metamodel file.

    Several ATL metamodels are ``xmi:XMI`` documents holding a ``PrimitiveTypes``
    package alongside the domain package. Reading the document root then yields
    no nsURI at all, which is how seven ATL contracts came to record an empty
    ``metamodelUri`` while every other language recorded a real one. Classifiers
    are still collected across the whole document, because a transformation may
    legitimately reference the primitive types declared beside the domain types.
    """
    root = ET.parse(path).getroot()
    package = _domain_package(root, preferred_package or path.stem)
    classifiers = tuple(
        str(element.get("name"))
        for element in root.iter()
        if element.tag.endswith("eClassifiers") and element.get("name")
    )
    return EcoreInfo(
        path=path,
        name=str(package.get("name") or path.stem),
        ns_uri=str(package.get("nsURI") or ""),
        ns_prefix=str(package.get("nsPrefix") or ""),
        classifiers=classifiers,
    )


def _domain_package(root: ET.Element, preferred: str) -> ET.Element:
    """The EPackage a contract should quote, not the document root."""
    if root.tag.endswith("EPackage"):
        return root
    packages = [element for element in root.iter() if element.tag.endswith("EPackage")]
    if not packages:
        raise ValueError(f"no EPackage in metamodel document: {preferred}")
    named = [
        package
        for package in packages
        if str(package.get("name") or "").lower() == preferred.lower()
    ]
    if named:
        return named[0]
    domain = [
        package for package in packages if package.get("name") != "PrimitiveTypes"
    ]
    return (domain or packages)[0]


BUILDERS = {
    "etl": build_etl_contract,
    "atl": build_atl_contract,
    "qvto": build_qvto_contract,
    "reactions": build_reactions_contract,
}

REFERENCE_EXTENSIONS = {
    "etl": ".etl",
    "atl": ".atl",
    "qvto": ".qvto",
    "reactions": ".reactions",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
