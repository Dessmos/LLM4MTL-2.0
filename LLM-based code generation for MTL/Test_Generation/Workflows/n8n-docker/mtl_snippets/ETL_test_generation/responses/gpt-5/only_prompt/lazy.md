```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Graph2TreeSemanticCases",
  "transformation": {
    "path": "transformations/Graph2Tree.etl",
    "entryRule": null
  },
  "metamodels": [
    {
      "role": "source",
      "path": "metamodels/Graph.ecore",
      "metamodelUri": "Graph"
    },
    {
      "role": "target",
      "path": "metamodels/Tree.ecore",
      "metamodelUri": "Tree"
    }
  ],
  "tests": [
    {
      "name": "single_node_graph_to_single_tree",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/single_node_graph.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "path": "models/single_node_graph_out.model",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "equals": 1
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Tree",
          "matchBy": "label",
          "values": [
            {
              "match": "A",
              "features": {
                "label": "A"
              }
            }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "type": "Tree",
          "reference": "children",
          "pairs": []
        },
        {
          "kind": "objects",
          "model": "OUT",
          "type": "Tree",
          "ids": [
            "A"
          ],
          "idFeature": "label"
        }
      ]
    },
    {
      "name": "branching_graph_preserves_direction",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/branching_graph.model",
          "generated": true,
          "metamodelUri": "Graph"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "path": "models/branching_graph_out.model",
          "generated": false,
          "metamodelUri": "Tree"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Tree",
          "equals": 3
        },
        {
          "kind": "objects",
          "model": "OUT",
          "type": "Tree",
          "ids": [
            "A",
            "B",
            "C"
          ],
          "idFeature": "label"
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "type": "Tree",
          "reference": "children",
          "pairs": [
            {
              "sourceId": "A",
              "targetId": "B"
            },
            {
              "sourceId": "A",
              "targetId": "C"
            }
          ],
          "idFeature": "label"
        },
        {
          "kind": "pathValues",
          "model": "OUT",
          "paths": [
            {
              "from": "A",
              "via": "children",
              "values": [
                "B",
                "C"
              ],
              "idFeature": "label"
            },
            {
              "from": "B",
              "via": "children",
              "values": [],
              "idFeature": "label"
            },
            {
              "from": "C",
              "via": "children",
              "values": [],
              "idFeature": "label"
            }
          ]
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
  <nodes xsi:type="Graph:Node" name="A"/>
</Graph:Graph>
```

```xml file=models/branching_graph.model
<?xml version="1.0" encoding="UTF-8"?>
<Graph:Graph xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:Graph="Graph">
  <nodes xsi:type="Graph:Node" name="A" outgoing="//@nodes.1/@incoming.0 //@nodes.2/@incoming.0"/>
  <nodes xsi:type="Graph:Node" name="B" incoming="//@nodes.0/@outgoing.0"/>
  <nodes xsi:type="Graph:Node" name="C" incoming="//@nodes.0/@outgoing.1"/>
</Graph:Graph>
```