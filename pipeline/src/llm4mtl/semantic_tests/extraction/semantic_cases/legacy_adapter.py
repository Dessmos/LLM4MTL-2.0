"""Adapter for the legacy Tree2Graph expectedNodes/expectedEdges spec shape."""

from __future__ import annotations

from typing import Any


def is_legacy_tree2graph_spec(spec: dict[str, Any]) -> bool:
    tests = spec.get("tests")
    return (
        isinstance(tests, list)
        and bool(tests)
        and "models" not in spec
        and any(isinstance(test, dict) and "expectedNodes" in test for test in tests)
    )


def normalize_legacy_tree2graph_spec(spec: dict[str, Any]) -> dict[str, Any]:
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
                    {"kind": "count", "model": "Graph", "type": "Node", "expected": len(nodes)},
                    {"kind": "count", "model": "Graph", "type": "Edge", "expected": len(edges)},
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
                        "expected": [{"source": edge.split("->", 1)[0], "target": edge.split("->", 1)[1]} for edge in edges],
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
    if not isinstance(raw_nodes, list):
        raise SystemExit("expectedNodes must be an array")
    names: list[str] = []
    for node in raw_nodes:
        if isinstance(node, str):
            names.append(node)
        elif isinstance(node, dict) and isinstance(node.get("name"), str):
            names.append(node["name"])
        else:
            raise SystemExit("expectedNodes entries must be strings or objects with a name")
    return names


def expected_edge_pairs(raw_edges: Any) -> list[str]:
    if not isinstance(raw_edges, list):
        raise SystemExit("expectedEdges must be an array")
    pairs: list[str] = []
    for edge in raw_edges:
        if not isinstance(edge, dict) or not edge.get("source") or not edge.get("target"):
            raise SystemExit("expectedEdges entries must contain source and target")
        pairs.append(f"{edge['source']}->{edge['target']}")
    return pairs
