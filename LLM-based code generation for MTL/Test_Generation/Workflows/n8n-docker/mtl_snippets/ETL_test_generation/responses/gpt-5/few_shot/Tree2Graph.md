```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedTree2GraphSemanticTests",
  "transformation": "Tree2Graph.etl",
  "metamodels": [
    {
      "name": "Tree",
      "uri": "Tree"
    },
    {
      "name": "Graph",
      "uri": "Graph"
    }
  ],
  "tests": [
    {
      "name": "single_root_tree_creates_one_node_and_no_edges",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/single_root.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Graph",
          "type": "Node",
          "expected": 1
        },
        {
          "kind": "count",
          "model": "Graph",
          "type": "Edge",
          "expected": 0
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": [
            "root"
          ]
        }
      ]
    },
    {
      "name": "two_level_tree_creates_parent_child_edge",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/two_level.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Graph",
          "type": "Node",
          "expected": 2
        },
        {
          "kind": "count",
          "model": "Graph",
          "type": "Edge",
          "expected": 1
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": [
            "child",
            "root"
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Graph",
          "type": "Edge",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            {
              "source": "root",
              "target": "child"
            }
          ]
        }
      ]
    },
    {
      "name": "branching_tree_with_duplicate_and_empty_labels_creates_exact_nodes_and_edges",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/branching_duplicates_empty.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "Graph",
          "type": "Node",
          "expected": 5
        },
        {
          "kind": "count",
          "model": "Graph",
          "type": "Edge",
          "expected": 4
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": [
            "",
            "A",
            "A",
            "B",
            "root"
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Graph",
          "type": "Edge",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            {
              "source": "A",
              "target": ""
            },
            {
              "source": "A",
              "target": "B"
            },
            {
              "source": "root",
              "target": "A"
            },
            {
              "source": "root",
              "target": "A"
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/single_root.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root"/>
```

```xml file=models/two_level.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="child"/>
</Tree:Tree>
```

```xml file=models/branching_duplicates_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="A">
    <children label="B"/>
  </children>
  <children label="A">
    <children label=""/>
  </children>
</Tree:Tree>
```