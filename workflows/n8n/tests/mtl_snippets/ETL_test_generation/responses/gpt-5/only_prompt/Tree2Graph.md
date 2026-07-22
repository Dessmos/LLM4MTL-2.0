```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Tree2GraphSemanticCases",
  "transformation": "Tree2Graph.etl",
  "metamodels": [
    { "name": "Tree", "uri": "Tree" },
    { "name": "Graph", "uri": "Graph" }
  ],
  "tests": [
    {
      "name": "single_root_tree_produces_one_node_and_no_edges",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/single_root.model",
          "generated": false,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Graph", "type": "Node", "expected": 1 },
        { "kind": "count", "model": "Graph", "type": "Edge", "expected": 0 },
        {
          "kind": "objects",
          "model": "Graph",
          "type": "Node",
          "features": ["name"],
          "expected": [
            { "name": "root" }
          ]
        },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": ["root"]
        }
      ]
    },
    {
      "name": "root_with_two_children_produces_three_nodes_and_two_edges",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/root_two_children.model",
          "generated": false,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Graph", "type": "Node", "expected": 3 },
        { "kind": "count", "model": "Graph", "type": "Edge", "expected": 2 },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": ["c1", "c2", "root"]
        },
        {
          "kind": "referencePairs",
          "model": "Graph",
          "type": "Edge",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            { "source": "root", "target": "c1" },
            { "source": "root", "target": "c2" }
          ]
        }
      ]
    },
    {
      "name": "three_level_chain_produces_parent_to_child_edge_direction",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/three_level_chain.model",
          "generated": false,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Graph", "type": "Node", "expected": 3 },
        { "kind": "count", "model": "Graph", "type": "Edge", "expected": 2 },
        {
          "kind": "objects",
          "model": "Graph",
          "type": "Node",
          "features": ["name"],
          "expected": [
            { "name": "grand" },
            { "name": "parent" },
            { "name": "child" }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "Graph",
          "type": "Edge",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            { "source": "grand", "target": "parent" },
            { "source": "parent", "target": "child" }
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_labels_preserved_in_node_names",
      "models": [
        {
          "name": "Tree",
          "kind": "emf",
          "role": "source",
          "path": "models/duplicate_empty_labels.model",
          "generated": false,
          "metamodelUri": "Tree"
        },
        {
          "name": "Graph",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Graph", "type": "Node", "expected": 3 },
        { "kind": "count", "model": "Graph", "type": "Edge", "expected": 2 },
        {
          "kind": "featureValues",
          "model": "Graph",
          "type": "Node",
          "feature": "name",
          "expected": ["", "dup", "dup"]
        },
        {
          "kind": "referencePairs",
          "model": "Graph",
          "type": "Edge",
          "source": "source.name",
          "target": "target.name",
          "expected": [
            { "source": "dup", "target": "dup" },
            { "source": "dup", "target": "" }
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

```xml file=models/root_two_children.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="c1"/>
  <children label="c2"/>
</Tree:Tree>
```

```xml file=models/three_level_chain.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="grand">
  <children label="parent">
    <children label="child"/>
  </children>
</Tree:Tree>
```

```xml file=models/duplicate_empty_labels.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="dup">
  <children label="dup">
    <children label=""/>
  </children>
</Tree:Tree>
```