"""Adapter for the legacy Tree2Graph expectedNodes/expectedEdges spec shape."""

from __future__ import annotations

from typing import Any

from .errors import SemanticCasesError

_SOURCE_MODEL = "Tree"
_TARGET_MODEL = "Graph"
# Joins the source and target node names of one expected edge.
_EDGE_SEPARATOR = "->"


def is_legacy_tree2graph_spec(spec: dict[str, Any]) -> bool:
    """Return whether ``spec`` uses the pre-contract Tree2Graph shape."""
    tests = spec.get("tests")
    return (
        isinstance(tests, list)
        and bool(tests)
        and "models" not in spec
        and any(isinstance(test, dict) and "expectedNodes" in test for test in tests)
    )


def normalize_legacy_tree2graph_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert a legacy Tree2Graph specification to the canonical shape."""
    tests = [_canonical_test(test) for test in spec["tests"]]
    return {
        "schemaVersion": 1,
        "testClass": spec.get("testClass") or "GeneratedTree2GraphSemanticTest",
        "transformation": "transformations/Tree2Graph.etl",
        "metamodels": ["metamodels/Tree.ecore", "metamodels/Graph.ecore"],
        "tests": tests,
    }


def _canonical_test(test: dict[str, Any]) -> dict[str, Any]:
    """One legacy test as a canonical test over a Tree source and a Graph target."""
    nodes = expected_node_names(test["expectedNodes"])
    edges = expected_edge_pairs(test["expectedEdges"])
    return {
        "name": test["name"],
        "models": _tree2graph_models(test["inputModel"]),
        "assertions": _graph_assertions(nodes, edges),
    }


def _tree2graph_models(input_model: Any) -> list[dict[str, Any]]:
    return [
        {
            "name": _SOURCE_MODEL,
            "kind": "emf",
            "role": "source",
            "path": input_model,
            "generated": True,
            "metamodelUri": _SOURCE_MODEL,
        },
        {
            "name": _TARGET_MODEL,
            "kind": "emf",
            "role": "target",
            "metamodelUri": _TARGET_MODEL,
        },
    ]


def _graph_assertions(nodes: list[str], edges: list[str]) -> list[dict[str, Any]]:
    """Assert the node and edge counts, the node names and the edge pairs."""
    return [
        _graph_count("Node", len(nodes)),
        _graph_count("Edge", len(edges)),
        {
            "kind": "featureValues",
            "model": _TARGET_MODEL,
            "type": "Node",
            "feature": "name",
            "expected": nodes,
        },
        {
            "kind": "referencePairs",
            "model": _TARGET_MODEL,
            "type": "Edge",
            "source": "source.name",
            "target": "target.name",
            "expected": [_edge_endpoints(edge) for edge in edges],
        },
    ]


def _graph_count(type_name: str, expected: int) -> dict[str, Any]:
    return {
        "kind": "count",
        "model": _TARGET_MODEL,
        "type": type_name,
        "expected": expected,
    }


def _edge_endpoints(edge: str) -> dict[str, str]:
    source, target = edge.split(_EDGE_SEPARATOR, 1)
    return {"source": source, "target": target}


def expected_node_names(raw_nodes: Any) -> list[str]:
    """Return validated node names from the legacy expectation list."""
    if not isinstance(raw_nodes, list):
        raise SemanticCasesError("expectedNodes must be an array")
    names: list[str] = []
    for node in raw_nodes:
        if isinstance(node, str):
            names.append(node)
        elif isinstance(node, dict) and isinstance(node.get("name"), str):
            names.append(node["name"])
        else:
            raise SemanticCasesError(
                "expectedNodes entries must be strings or objects with a name"
            )
    return names


def expected_edge_pairs(raw_edges: Any) -> list[str]:
    """Return validated ``source->target`` pairs from legacy expectations."""
    if not isinstance(raw_edges, list):
        raise SemanticCasesError("expectedEdges must be an array")
    pairs: list[str] = []
    for edge in raw_edges:
        if (
            not isinstance(edge, dict)
            or not edge.get("source")
            or not edge.get("target")
        ):
            raise SemanticCasesError(
                "expectedEdges entries must contain source and target"
            )
        pairs.append(f"{edge['source']}{_EDGE_SEPARATOR}{edge['target']}")
    return pairs
