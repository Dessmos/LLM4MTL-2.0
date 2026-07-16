```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Tree2GraphSemanticTests",
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
          "path": "models/tree_single_root.model",
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
      "name": "parent_and_child_create_two_nodes_and_one_edge_parent_to_child",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/tree_parent_child.model",
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
      "name": "three_level_tree_creates_chain_of_edges",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/tree_three_levels.model",
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
          "expected": 3
        },
        {
          "kind": "count",
          "model": "Graph",
          "type": "Edge",
          "expected": 2
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": [
            "child",
            "grandchild",
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
            },
            {
              "source": "child",
              "target": "grandchild"
            }
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_labels_are_preserved_in_node_names",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/tree_duplicate_empty_labels.model",
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
          "expected": 3
        },
        {
          "kind": "count",
          "model": "Graph",
          "type": "Edge",
          "expected": 2
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": [
            "",
            "",
            "same"
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
              "source": "",
              "target": "same"
            },
            {
              "source": "same",
              "target": ""
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/tree_single_root.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root"/>
```

```xml file=models/tree_parent_child.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="child"/>
</Tree:Tree>
```

```xml file=models/tree_three_levels.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="child">
    <children label="grandchild"/>
  </children>
</Tree:Tree>
```

```xml file=models/tree_duplicate_empty_labels.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="">
  <children label="same">
    <children label=""/>
  </children>
</Tree:Tree>
```