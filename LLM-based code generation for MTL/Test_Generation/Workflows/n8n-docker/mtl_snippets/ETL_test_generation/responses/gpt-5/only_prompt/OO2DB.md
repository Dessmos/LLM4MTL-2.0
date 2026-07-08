```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticCases",
  "transformation": "Graph2Tree.etl",
  "metamodels": [
    {
      "name": "Graph",
      "uri": "Graph"
    },
    {
      "name": "Tree",
      "uri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "empty_graph_produces_no_tree_instances",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/empty_graph.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "Tree",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Tree",
          "type": "Tree",
          "equals": 0
        },
        {
          "kind": "objects",
          "model": "Tree",
          "type": "Tree",
          "match": "all",
          "equals": []
        }
      ]
    },
    {
      "name": "single_node_no_edges_maps_to_single_tree_node_without_parent_or_children",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/single_node.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "Tree",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Tree",
          "type": "Tree",
          "equals": 1
        },
        {
          "kind": "featureValues",
          "model": "Tree",
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
          "model": "Tree",
          "type": "Tree",
          "idFeature": "label",
          "expected": [
            {
              "id": "A",
              "path": "parent.label",
              "values": []
            },
            {
              "id": "A",
              "path": "children.label",
              "values": []
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "sourceType": "Tree",
          "sourceIdFeature": "label",
          "reference": "children",
          "targetType": "Tree",
          "targetIdFeature": "label",
          "pairs": []
        }
      ]
    },
    {
      "name": "two_nodes_one_directed_edge_creates_parent_child_link_source_to_target",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/two_nodes_one_edge.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "Tree",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Tree",
          "type": "Tree",
          "equals": 2
        },
        {
          "kind": "objects",
          "model": "Tree",
          "type": "Tree",
          "idFeature": "label",
          "match": "all",
          "equals": ["A", "B"]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "sourceType": "Tree",
          "sourceIdFeature": "label",
          "reference": "children",
          "targetType": "Tree",
          "targetIdFeature": "label",
          "pairs": [
            ["A", "B"]
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "sourceType": "Tree",
          "sourceIdFeature": "label",
          "reference": "parent",
          "targetType": "Tree",
          "targetIdFeature": "label",
          "pairs": [
            ["B", "A"]
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph"/>
```

```xml file=models/single_node.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/two_nodes_one_edge.model
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