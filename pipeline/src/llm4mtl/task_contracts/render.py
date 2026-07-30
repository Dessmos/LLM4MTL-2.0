"""Human-readable rendering of a task contract.

Every contract is written twice: the ``.json`` the pipeline enforces, and the
``.txt`` rendered here for review. The table is deliberately language-neutral —
it names the transformation's runtime slots, not any one language's concepts —
so a reviewer reads ETL, ATL, QVT-O, and Reactions contracts the same way.

This is review material, not prompt material: the raw contract never reaches an
LLM. The prompt-generation stage receives the reference, the exact metamodel
files the contract selects, and the grammar.
"""

from __future__ import annotations

from llm4mtl.task_contracts.models import TaskContract


def contract_header_markdown(contract: TaskContract) -> str:
    """Render the authoritative model-contract table and rules."""
    lines = [
        "## Deterministic model contract (preflight)",
        "",
        "Use this contract as ground truth. Do not infer or invent model names, "
        "metamodel URIs, XML namespaces, or type names.",
        "",
        "| Runtime model name | Role(s) | Kind | metamodelUri | XML nsPrefix | "
        "Types used by the transformation |",
        "|---|---|---|---|---|---|",
    ]
    for model in contract.models:
        lines.append(
            "| {name} | {roles} | {kind} | {uri} | {prefix} | {types} |".format(
                name=model.runtime_name,
                roles=", ".join(model.roles),
                kind=model.kind,
                uri=model.metamodel_uri or "",
                prefix=model.metamodel_ns_prefix or "",
                types=", ".join(model.types_used_in_transformation),
            )
        )
    lines.extend(
        [
            "",
            "Mandatory rules:",
            "- In semantic_cases.json, each models[].name must equal one runtime model name above exactly.",
            "- For EMF models, each models[].metamodelUri must equal the listed metamodelUri exactly; "
            "do not use the Ecore file stem when it differs.",
            "- For generated EMF/XMI model files, use the listed XML nsPrefix and metamodelUri exactly "
            "in xmlns declarations.",
            '- For plainXml models, use kind="plainXml" and omit metamodelUri.',
            "- Do not mention or use any model/metamodel/type that is not listed in this contract.",
        ]
    )
    return "\n".join(lines)
