```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticTests",
  "transformation": "Graph2Tree",
  "metamodels": [
    {
      "name": "Graph",
      "role": "source",
      "kind": "emf",
      "metamodelUri": "Graph"
    },
    {
      "name": "Tree",
      "role": "target",
      "kind": "emf",
      "metamodelUri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "single_node_graph_maps_to_single_tree_root",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "generated": true,
          "path": "models/single_node_graph.model",
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
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "parent",
          "pairs": []
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "children",
          "pairs": []
        }
      ]
    },
    {
      "name": "linear_two_node_graph_maps_to_parent_child_tree",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "generated": true,
          "path": "models/two_node_linear_graph.model",
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
          "idFeature": "label"
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "parent",
          "pairs": [
            ["B", "A"]
          ],
          "idFeature": "label"
        }
      ]
    },
    {
      "name": "branching_graph_maps_to_branching_tree_structure",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "generated": true,
          "path": "models/branching_graph.model",
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
          "values": ["Root", "Left", "Right"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "children",
          "pairs": [
            ["Root", "Left"],
            ["Root", "Right"]
          ],
          "idFeature": "label"
        },
        {
          "kind": "referencePairs",
          "type": "Tree!Tree",
          "reference": "parent",
          "pairs": [
            ["Left", "Root"],
            ["Right", "Root"]
          ],
          "idFeature": "label"
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
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/two_node_linear_graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes name="A">
    <outgoing target="//@nodes.1"/>
  </nodes>
  <nodes name="B"/>
</Graph:Graph>
```

```xml file=models/branching_graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes name="Root">
    <outgoing target="//@nodes.1"/>
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="Left"/>
  <nodes name="Right"/>
</Graph:Graph>
```