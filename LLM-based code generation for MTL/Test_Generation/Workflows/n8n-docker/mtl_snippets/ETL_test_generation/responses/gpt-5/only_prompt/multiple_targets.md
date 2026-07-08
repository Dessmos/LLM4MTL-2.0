```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticTests",
  "transformation": "Graph2Tree",
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
      "name": "single_node_no_edges",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/single_node_no_edges.model",
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
          "value": 1
        },
        {
          "kind": "featureValues",
          "model": "Tree",
          "type": "Tree",
          "idFeature": "label",
          "feature": "label",
          "pairs": [
            {
              "id": "A",
              "value": "A"
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "children",
          "pairs": []
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "parent",
          "pairs": []
        }
      ]
    },
    {
      "name": "two_nodes_one_edge",
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
          "value": 2
        },
        {
          "kind": "objects",
          "model": "Tree",
          "type": "Tree",
          "idFeature": "label",
          "ids": ["A", "B"]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "children",
          "pairs": [
            {
              "source": "A",
              "target": "B"
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "parent",
          "pairs": [
            {
              "source": "B",
              "target": "A"
            }
          ]
        }
      ]
    },
    {
      "name": "branching_root_two_children",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/branching_root_two_children.model",
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
          "value": 3
        },
        {
          "kind": "objects",
          "model": "Tree",
          "type": "Tree",
          "idFeature": "label",
          "ids": ["R", "C1", "C2"]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "children",
          "pairs": [
            {
              "source": "R",
              "target": "C1"
            },
            {
              "source": "R",
              "target": "C2"
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Tree",
          "type": "Tree",
          "sourceIdFeature": "label",
          "targetIdFeature": "label",
          "reference": "parent",
          "pairs": [
            {
              "source": "C1",
              "target": "R"
            },
            {
              "source": "C2",
              "target": "R"
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/single_node_no_edges.model
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

```xml file=models/branching_root_two_children.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="R">
    <outgoing target="//@nodes.1"/>
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="C1"/>
  <nodes name="C2"/>
</Graph:Graph>
```