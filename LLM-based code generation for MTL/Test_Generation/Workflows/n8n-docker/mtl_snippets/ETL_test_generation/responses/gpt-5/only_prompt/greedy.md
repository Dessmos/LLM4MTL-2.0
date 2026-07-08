```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticCases",
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
      "name": "single_node_no_edges",
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
          "type": "Tree::Tree",
          "equals": 1
        },
        {
          "kind": "featureValues",
          "type": "Tree::Tree",
          "feature": "label",
          "values": ["A"]
        },
        {
          "kind": "featureValues",
          "type": "Tree::Tree",
          "feature": "parent",
          "values": [null]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": []
        }
      ]
    },
    {
      "name": "linear_three_nodes",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/linear_three.model",
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
          "type": "Tree::Tree",
          "equals": 3
        },
        {
          "kind": "featureValues",
          "type": "Tree::Tree",
          "feature": "label",
          "values": ["A", "B", "C"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": [
            ["A", "B"],
            ["B", "C"]
          ]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "parent",
          "pairs": [
            ["B", "A"],
            ["C", "B"]
          ]
        }
      ]
    },
    {
      "name": "branching_outgoing_edges",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/branching.model",
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
          "type": "Tree::Tree",
          "equals": 3
        },
        {
          "kind": "featureValues",
          "type": "Tree::Tree",
          "feature": "label",
          "values": ["Root", "Left", "Right"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": [
            ["Root", "Left"],
            ["Root", "Right"]
          ]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "parent",
          "pairs": [
            ["Left", "Root"],
            ["Right", "Root"]
          ]
        }
      ]
    },
    {
      "name": "empty_graph_no_nodes",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/empty.model",
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
          "type": "Tree::Tree",
          "equals": 0
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "ids": []
        }
      ]
    }
  ]
}
```

```xml file=models/single_node.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/linear_three.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A">
    <outgoing target="//@nodes.1"/>
  </nodes>
  <nodes name="B">
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="C"/>
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

```xml file=models/empty.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph"/>
```