"""Adapter for the legacy Tree2Graph expectedNodes/expectedEdges spec shape."""

from __future__ import annotations

from typing import Any

from .errors import SemanticCasesError


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
    tests = []
    for test in spec["tests"]:
        nodes = expected_node_names(test["expectedNodes"])
        edges = expected_edge_pairs(test["expectedEdges"])
        tests.append(
            {
                "name": test["name"],
                "models": [
                    {
                        "name": "Tree",
                        "kind": "emf",
                        "role": "source",
                        "path": test["inputModel"],
                        "generated": True,
                        "metamodelUri": "Tree",
                    },
                    {
                        "name": "Graph",
                        "kind": "emf",
                        "role": "target",
                        "metamodelUri": "Graph",
                    },
                ],
                "assertions": [
                    {
                        "kind": "count",
                        "model": "Graph",
                        "type": "Node",
                        "expected": len(nodes),
                    },
                    {
                        "kind": "count",
                        "model": "Graph",
                        "type": "Edge",
                        "expected": len(edges),
                    },
                    {
                        "kind": "featureValues",
                        "model": "Graph",
                        "type": "Node",
                        "feature": "name",
                        "expected": nodes,
                    },
                    {
                        "kind": "referencePairs",
                        "model": "Graph",
                        "type": "Edge",
                        "source": "source.name",
                        "target": "target.name",
                        "expected": [
                            {
                                "source": edge.split("->", 1)[0],
                                "target": edge.split("->", 1)[1],
                            }
                            for edge in edges
                        ],
                    },
                ],
            }
        )

    return {
        "schemaVersion": 1,
        "testClass": spec.get("testClass") or "GeneratedTree2GraphSemanticTest",
        "transformation": "transformations/Tree2Graph.etl",
        "metamodels": ["metamodels/Tree.ecore", "metamodels/Graph.ecore"],
        "tests": tests,
    }


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
        pairs.append(f"{edge['source']}->{edge['target']}")
    return pairs
