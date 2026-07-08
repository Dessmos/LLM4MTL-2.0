```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticTests",
  "transformation": "Graph2Tree",
  "metamodels": [
    {
      "name": "IN",
      "kind": "emf",
      "role": "source",
      "metamodelUri": "Graph"
    },
    {
      "name": "OUT",
      "kind": "emf",
      "role": "target",
      "metamodelUri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "empty_graph_produces_no_tree_nodes",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/empty-graph.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "value": 0
        },
        {
          "kind": "objects",
          "model": "OUT",
          "type": "Tree",
          "match": []
        }
      ]
    },
    {
      "name": "single_node_graph_maps_to_single_root_tree",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/single-node.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "value": 1
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Tree",
          "idFeature": "label",
          "expected": [
            {
              "id": "A",
              "values": {
                "label": "A"
              }
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "OUT",
          "type": "Tree",
          "expected": [
            {
              "idFeature": "label",
              "id": "A",
              "path": "parent",
              "value": null
            },
            {
              "idFeature": "label",
              "id": "A",
              "path": "children",
              "value": []
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "reference": "children",
          "sourceType": "Tree",
          "targetType": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "pairs": []
        }
      ]
    },
    {
      "name": "two_node_one_edge_creates_parent_child_direction",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/two-nodes-one-edge.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "value": 2
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Tree",
          "idFeature": "label",
          "expected": [
            {
              "id": "A",
              "values": {
                "label": "A"
              }
            },
            {
              "id": "B",
              "values": {
                "label": "B"
              }
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "reference": "children",
          "sourceType": "Tree",
          "targetType": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "pairs": [
            {
              "source": "A",
              "target": "B"
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "OUT",
          "type": "Tree",
          "expected": [
            {
              "idFeature": "label",
              "id": "B",
              "path": "parent.label",
              "value": "A"
            }
          ]
        }
      ]
    },
    {
      "name": "branching_from_one_source_creates_multiple_children",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/branching.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "value": 3
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Tree",
          "idFeature": "label",
          "expected": [
            {
              "id": "Root",
              "values": {
                "label": "Root"
              }
            },
            {
              "id": "Left",
              "values": {
                "label": "Left"
              }
            },
            {
              "id": "Right",
              "values": {
                "label": "Right"
              }
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "reference": "children",
          "sourceType": "Tree",
          "targetType": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "pairs": [
            {
              "source": "Root",
              "target": "Left"
            },
            {
              "source": "Root",
              "target": "Right"
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "OUT",
          "type": "Tree",
          "expected": [
            {
              "idFeature": "label",
              "id": "Left",
              "path": "parent.label",
              "value": "Root"
            },
            {
              "idFeature": "label",
              "id": "Right",
              "path": "parent.label",
              "value": "Root"
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty-graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph"/>
```

```xml file=models/single-node.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/two-nodes-one-edge.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A">
    <outgoing target="//@nodes.1"/>
  </nodes>
  <nodes name="B"/>
</Graph:Graph>
```

```xml file=models/branching.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="Root">
    <outgoing target="//@nodes.1"/>
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="Left"/>
  <nodes name="Right"/>
</Graph:Graph>
```