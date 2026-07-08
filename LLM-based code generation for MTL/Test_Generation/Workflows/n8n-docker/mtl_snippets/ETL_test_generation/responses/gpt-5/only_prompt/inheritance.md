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
      "name": "singleNode_noEdges_producesSingleTreeNode",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/singleNode_noEdges.model",
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
          "key": "label",
          "values": ["A"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": []
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "A",
            "parent": null
          },
          "count": 1
        }
      ]
    },
    {
      "name": "twoNodes_oneEdge_producesParentChildDirection",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/twoNodes_oneEdge.model",
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
          "equals": 2
        },
        {
          "kind": "featureValues",
          "type": "Tree::Tree",
          "key": "label",
          "values": ["A", "B"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": [
            { "from": { "label": "A" }, "to": { "label": "B" } }
          ]
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "A",
            "parent": null
          },
          "count": 1
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "B",
            "parent": { "label": "A" }
          },
          "count": 1
        }
      ]
    },
    {
      "name": "branchingNode_multipleOutgoingEdges_producesMultipleChildren",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/branchingNode.model",
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
          "key": "label",
          "values": ["A", "B", "C"]
        },
        {
          "kind": "referencePairs",
          "type": "Tree::Tree",
          "reference": "children",
          "pairs": [
            { "from": { "label": "A" }, "to": { "label": "B" } },
            { "from": { "label": "A" }, "to": { "label": "C" } }
          ]
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "A",
            "parent": null
          },
          "count": 1
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "B",
            "parent": { "label": "A" }
          },
          "count": 1
        },
        {
          "kind": "objects",
          "type": "Tree::Tree",
          "match": {
            "label": "C",
            "parent": { "label": "A" }
          },
          "count": 1
        }
      ]
    }
  ]
}
```

```xml file=models/singleNode_noEdges.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/twoNodes_oneEdge.model
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

```xml file=models/branchingNode.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Graph="Graph">
  <nodes name="A">
    <outgoing target="//@nodes.1"/>
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="B"/>
  <nodes name="C"/>
</Graph:Graph>
```