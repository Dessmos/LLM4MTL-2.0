"""Build deterministic ETL task model contracts for prompt preflight.

The contract separates ETL runtime model names from EMF metamodel URIs. This
matters for examples such as Flowchart, where the ETL prefix is "Flowchart" but
the registered Ecore nsURI is "flowchart", and OO2DB, where the runtime model
name "OO2DB" uses the TM metamodel.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.paths import default_etl_test_dir, default_responses_root, repo_root
from etl.contracts import TaskContract, contract_from_mapping
from etl.contracts.render import (
    CONTRACT_MARKER_END,
    CONTRACT_MARKER_START,
    TASK_CONTEXT_MARKER_END,
    TASK_CONTEXT_MARKER_START,
    contract_header_block,
    contract_header_markdown,
    task_context_block,
)
from etl.prompt_generation.injection import inject_marked_block


ETL_TYPE_RE = re.compile(r"\b([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")
TRANSFORM_RE = re.compile(r"\btransform\b[^:\n]*:\s*([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")
TO_RE = re.compile(r"\bto\b(?P<body>.*?)(?:\{|\n\s*\n)", re.DOTALL)
DECLARED_TYPE_RE = re.compile(r":\s*([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")
NEW_RE = re.compile(r"\bnew\s+([A-Za-z_]\w*)!\s*`?([A-Za-z_][\w:-]*)`?")


@dataclass(frozen=True)
class EcoreInfo:
    path: Path
    name: str
    ns_uri: str
    ns_prefix: str
    classifiers: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ETL prompt model contracts.")
    parser.add_argument(
        "--references-root",
        type=Path,
        default=default_responses_root().parent / "references",
        help="Directory containing reference ETL files.",
    )
    parser.add_argument(
        "--metamodels-root",
        type=Path,
        default=default_etl_test_dir() / "src/test/resources/metamodels",
        help="Directory containing Ecore metamodels.",
    )
    parser.add_argument(
        "--prompts-root",
        type=Path,
        default=default_responses_root().parent / "prompts/gpt-5",
        help="Prompt directory to enrich when --inject-prompts is set.",
    )
    parser.add_argument(
        "--contracts-root",
        type=Path,
        default=default_responses_root().parent / "task_contracts",
        help="Output directory for JSON and text contracts.",
    )
    parser.add_argument(
        "--inject-prompts",
        action="store_true",
        help="Insert deterministic contract text into existing prompt files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ecores = load_ecores(args.metamodels_root)
    args.contracts_root.mkdir(parents=True, exist_ok=True)

    for etl_path in sorted(args.references_root.glob("*.etl")):
        task = etl_path.stem
        contract = build_contract(task, etl_path, ecores)
        typed_contract = contract_from_mapping(contract, task)
        (args.contracts_root / f"{task}.json").write_text(
            json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (args.contracts_root / f"{task}.txt").write_text(
            contract_header_markdown(typed_contract) + "\n",
            encoding="utf-8",
        )
        if args.inject_prompts:
            inject_prompt_contracts(
                args.prompts_root / f"{task}.txt",
                typed_contract,
                etl_path.read_text(encoding="utf-8"),
            )

    return 0


def load_ecores(root: Path) -> list[EcoreInfo]:
    ecores = []
    for path in sorted(root.glob("*.ecore")):
        tree = ET.parse(path)
        package = tree.getroot()
        classifiers = []
        for element in package.iter():
            if element.tag.endswith("eClassifiers") and element.get("name"):
                classifiers.append(str(element.get("name")))
        ecores.append(
            EcoreInfo(
                path=path,
                name=str(package.get("name") or path.stem),
                ns_uri=str(package.get("nsURI") or ""),
                ns_prefix=str(package.get("nsPrefix") or ""),
                classifiers=tuple(classifiers),
            )
        )
    return ecores


def build_contract(task: str, etl_path: Path, ecores: list[EcoreInfo]) -> dict[str, Any]:
    code = etl_path.read_text(encoding="utf-8")
    prefix_types = collect_prefix_types(code)
    roles = collect_roles(code)

    models = []
    for prefix in sorted(prefix_types):
        model_types = sorted(prefix_types[prefix])
        ecore = resolve_ecore(prefix, model_types, ecores)
        model: dict[str, Any] = {
            "runtimeName": prefix,
            "roles": sorted(roles.get(prefix) or ["source"]),
            "typesUsedInEtL": model_types,
        }
        if ecore:
            model.update(
                {
                    "kind": "emf",
                    "metamodelUri": ecore.ns_uri,
                    "metamodelNsPrefix": ecore.ns_prefix,
                    "metamodelFile": relative(ecore.path),
                    "availableTypes": list(ecore.classifiers),
                }
            )
        else:
            model.update(
                {
                    "kind": "plainXml",
                    "metamodelUri": None,
                    "metamodelNsPrefix": None,
                    "metamodelFile": None,
                    "availableTypes": model_types,
                }
            )
        models.append(model)

    return {
        "task": task,
        "transformation": f"{task}.etl",
        "reference": relative(etl_path),
        "models": models,
        "rules": [
            "models[].name in semantic_cases.json must equal runtimeName exactly.",
            "For EMF models, models[].metamodelUri must equal metamodelUri exactly.",
            "For generated EMF XMI, XML namespace URI/prefix must use metamodelUri/metamodelNsPrefix exactly.",
            "For plainXml models, do not set metamodelUri and use kind='plainXml'.",
            "Do not invent model names, metamodel URIs, metamodel files, or type names outside this contract.",
        ],
    }


def collect_prefix_types(code: str) -> dict[str, set[str]]:
    prefix_types: dict[str, set[str]] = {}
    for prefix, type_name in ETL_TYPE_RE.findall(code):
        prefix_types.setdefault(prefix, set()).add(type_name)
    return prefix_types


def collect_roles(code: str) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    for prefix, _ in TRANSFORM_RE.findall(code):
        roles.setdefault(prefix, set()).add("source")
    for to_match in TO_RE.finditer(code):
        for prefix, _ in DECLARED_TYPE_RE.findall(to_match.group("body")):
            roles.setdefault(prefix, set()).add("target")
    for prefix, _ in NEW_RE.findall(code):
        roles.setdefault(prefix, set()).add("target")
    return roles


def resolve_ecore(prefix: str, types: list[str], ecores: list[EcoreInfo]) -> EcoreInfo | None:
    for ecore in ecores:
        if prefix in {ecore.ns_uri, ecore.ns_prefix, ecore.name}:
            return ecore
    type_matches = [ecore for ecore in ecores if all(type_name in ecore.classifiers for type_name in types)]
    if len(type_matches) == 1:
        return type_matches[0]
    if type_matches:
        return sorted(type_matches, key=lambda item: len(item.classifiers))[0]
    return None


def inject_prompt_contracts(
    prompt_path: Path,
    contract: TaskContract,
    reference_etl: str,
) -> None:
    """Overlay the deterministic contract header and task-context onto a prompt.

    The LLM-authored prompt keeps its framing/semantic guidance; the metamodel
    facts and the reference-ETL/task-context are replaced with the authoritative
    versions so the prompt can never disagree with the enforced contract.
    """
    if not prompt_path.exists():
        return
    text = prompt_path.read_text(encoding="utf-8")
    text = inject_marked_block(
        text,
        CONTRACT_MARKER_START,
        CONTRACT_MARKER_END,
        contract_header_block(contract),
    )
    text = inject_marked_block(
        text,
        TASK_CONTEXT_MARKER_START,
        TASK_CONTEXT_MARKER_END,
        task_context_block(contract, reference_etl),
        anchor_after=CONTRACT_MARKER_END,
    )
    prompt_path.write_text(text, encoding="utf-8")


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
