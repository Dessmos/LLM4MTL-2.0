```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticTests",
  "transformation": "Graph2Tree.etl",
  "metamodels": [
    {
      "name": "Graph",
      "kind": "emf",
      "role": "source",
      "metamodelUri": "Graph"
    },
    {
      "name": "Tree",
      "kind": "emf",
      "role": "target",
      "metamodelUri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "minimal_single_node_no_edges",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/minimal_single_node_no_edges.model",
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
          "value": 1
        },
        {
          "kind": "featureValues",
          "type": "Tree!Tree",
          "where": {
            "label": "A"
          },
          "feature": "label",
          "values": [
            "A"
          ]
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "A"
          },
          "path": "children.label",
          "values": []
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "A"
          },
          "path": "parent.label",
          "values": []
        },
        {
          "kind": "objects",
          "type": "Tree!Tree",
          "ids": [
            {
              "label": "A"
            }
          ]
        }
      ]
    },
    {
      "name": "multi_node_with_branching_and_chain",
      "models": [
        {
          "name": "Graph",
          "kind": "emf",
          "role": "source",
          "path": "models/multi_node_with_branching_and_chain.model",
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
          "value": 4
        },
        {
          "kind": "objects",
          "type": "Tree!Tree",
          "ids": [
            {
              "label": "N1"
            },
            {
              "label": "N2"
            },
            {
              "label": "N3"
            },
            {
              "label": "N4"
            }
          ]
        },
        {
          "kind": "referencePairs",
          "sourceType": "Tree!Tree",
          "sourceWhere": {
            "label": "N1"
          },
          "reference": "children",
          "targetType": "Tree!Tree",
          "pairs": [
            {
              "source": {
                "label": "N1"
              },
              "target": {
                "label": "N2"
              }
            },
            {
              "source": {
                "label": "N1"
              },
              "target": {
                "label": "N3"
              }
            },
            {
              "source": {
                "label": "N2"
              },
              "target": {
                "label": "N4"
              }
            }
          ]
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N1"
          },
          "path": "parent.label",
          "values": []
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N2"
          },
          "path": "parent.label",
          "values": [
            "N1"
          ]
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N3"
          },
          "path": "parent.label",
          "values": [
            "N1"
          ]
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N4"
          },
          "path": "parent.label",
          "values": [
            "N2"
          ]
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N3"
          },
          "path": "children.label",
          "values": []
        },
        {
          "kind": "pathValues",
          "sourceType": "Tree!Tree",
          "where": {
            "label": "N4"
          },
          "path": "children.label",
          "values": []
        }
      ]
    }
  ]
}
```

```xml file=models/minimal_single_node_no_edges.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes name="A"/>
</Graph:Graph>
```

```xml file=models/multi_node_with_branching_and_chain.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes name="N1">
    <outgoing target="//@nodes.1"/>
    <outgoing target="//@nodes.2"/>
  </nodes>
  <nodes name="N2">
    <outgoing target="//@nodes.3"/>
  </nodes>
  <nodes name="N3"/>
  <nodes name="N4"/>
</Graph:Graph>
```