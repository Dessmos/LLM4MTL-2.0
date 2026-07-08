```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticTests",
  "transformation": "Graph2Tree.etl",
  "metamodels": [
    {
      "name": "GraphMM",
      "kind": "emf",
      "metamodelUri": "Graph"
    },
    {
      "name": "TreeMM",
      "kind": "emf",
      "metamodelUri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "single_node_graph_to_single_tree_root",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/single_node_graph.model",
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
          "type": "Tree!Tree",
          "equals": 1
        },
        {
          "kind": "featureValues",
          "type": "Tree!Tree",
          "feature": "label",
          "values": ["A"]
        },
        {
          "kind": "count",
          "type": "Tree!Tree.children",
          "equals": 0
        },
        {
          "kind": "count",
          "type": "Tree!Tree.parent",
          "equals": 0
        }
      ]
    },
    {
      "name": "two_nodes_one_edge_parent_child_direction",
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
          "type": "Tree!Tree",
          "equals": 2
        },
        {
          "kind": "featureValues",
          "type": "Tree!Tree",
          "feature": "label",
          "values": ["A", "B"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "children",
          "pairs": [
            ["A", "B"]
          ],
          "keyFeature": "label"
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "parent",
          "pairs": [
            ["B", "A"]
          ],
          "keyFeature": "label"
        },
        {
          "kind": "count",
          "type": "Tree!Tree.children",
          "equals": 1
        },
        {
          "kind": "count",
          "type": "Tree!Tree.parent",
          "equals": 1
        }
      ]
    },
    {
      "name": "branching_graph_preserves_multiple_children",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/branching_graph.model",
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
          "type": "Tree!Tree",
          "equals": 3
        },
        {
          "kind": "featureValues",
          "type": "Tree!Tree",
          "feature": "label",
          "values": ["Root", "L", "R"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "children",
          "pairs": [
            ["Root", "L"],
            ["Root", "R"]
          ],
          "keyFeature": "label"
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "parent",
          "pairs": [
            ["L", "Root"],
            ["R", "Root"]
          ],
          "keyFeature": "label"
        },
        {
          "kind": "count",
          "type": "Tree!Tree.children",
          "equals": 2
        },
        {
          "kind": "count",
          "type": "Tree!Tree.parent",
          "equals": 2
        }
      ]
    }
  ]
}
```

```xml file=models/single_node_graph.model
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
  <nodes xmi:id="n1" name="A">
    <outgoing target="#n2"/>
  </nodes>
  <nodes xmi:id="n2" name="B"/>
</Graph:Graph>
```

```xml file=models/branching_graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes xmi:id="nRoot" name="Root">
    <outgoing target="#nL"/>
    <outgoing target="#nR"/>
  </nodes>
  <nodes xmi:id="nL" name="L"/>
  <nodes xmi:id="nR" name="R"/>
</Graph:Graph>
```