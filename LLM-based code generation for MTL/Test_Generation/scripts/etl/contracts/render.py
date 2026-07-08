"""Markdown rendering of a task contract for prompt construction.

Both the injected contract header and the deterministic "Task context" block of
a test-generation prompt are rendered from the same ``TaskContract`` here, so
prompts can never disagree with the enforced ground truth.
"""

from __future__ import annotations

from etl.contracts.models import ModelContract, TaskContract


CONTRACT_MARKER_START = "<!-- BEGIN deterministic-model-contract -->"
CONTRACT_MARKER_END = "<!-- END deterministic-model-contract -->"

TASK_CONTEXT_MARKER_START = "<!-- BEGIN deterministic-task-context -->"
TASK_CONTEXT_MARKER_END = "<!-- END deterministic-task-context -->"


def contract_header_markdown(contract: TaskContract) -> str:
    """Render the authoritative model-contract table and rules."""
    lines = [
        "## Deterministic model contract (preflight)",
        "",
        "Use this contract as ground truth. Do not infer or invent model names, "
        "metamodel URIs, XML namespaces, or type names.",
        "",
        "| Runtime model name | Role(s) | Kind | metamodelUri | XML nsPrefix | Types used by ETL |",
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
                types=", ".join(model.types_used_in_etl),
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


def contract_header_block(contract: TaskContract) -> str:
    """The contract header wrapped in the injection markers."""
    return "\n".join(
        [
            CONTRACT_MARKER_START,
            contract_header_markdown(contract),
            CONTRACT_MARKER_END,
        ]
    )


def task_context_markdown(contract: TaskContract, reference_etl: str) -> str:
    """Render the deterministic transformation + metamodels block.

    This replaces free-text, LLM-authored transformation descriptions (the
    source of Tree2Graph leakage) with the verbatim reference ETL and the exact
    metamodels taken from the contract.
    """
    lines = [
        "## Task context (must be used as ground truth)",
        "",
        f"- Transformation file: `{contract.transformation}`",
        "- ETL rules (authoritative — derive every expected fact only from these):",
        "",
        "```etl",
        reference_etl.strip("\n"),
        "```",
        "",
        "- Metamodels for this task (from the deterministic contract; do not use any others):",
    ]
    for model in contract.models:
        lines.append(f"  - {_model_context_line(model)}")
    return "\n".join(lines)


def task_context_block(contract: TaskContract, reference_etl: str) -> str:
    """The task-context section wrapped in the injection markers."""
    return "\n".join(
        [
            TASK_CONTEXT_MARKER_START,
            task_context_markdown(contract, reference_etl),
            TASK_CONTEXT_MARKER_END,
        ]
    )


def _model_context_line(model: ModelContract) -> str:
    roles = "/".join(model.roles)
    types = ", ".join(model.types_used_in_etl) or "(none referenced by the ETL)"
    if model.kind == "emf":
        return (
            f"`{model.runtime_name}` ({roles}, emf, metamodelUri `{model.metamodel_uri}`): "
            f"types {types}"
        )
    return f"`{model.runtime_name}` ({roles}, plainXml): elements {types}"
