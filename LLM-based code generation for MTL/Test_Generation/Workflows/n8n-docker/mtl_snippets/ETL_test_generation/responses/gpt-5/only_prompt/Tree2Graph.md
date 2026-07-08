```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Tree2GraphSemanticTests",
  "transformation": "Tree2Graph",
  "metamodels": [
    {
      "name": "IN",
      "kind": "emf",
      "role": "source",
      "metamodelUri": "Tree"
    },
    {
      "name": "OUT",
      "kind": "emf",
      "role": "target",
      "metamodelUri": "Graph"
    }
  ],
  "tests": [
    {
      "name": "single_root_no_children",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/single_root.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Graph",
          "equals": 1
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Node",
          "equals": 1
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Edge",
          "equals": 0
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Node",
          "idFeature": "name",
          "expected": [
            {
              "id": "root",
              "values": {
                "name": "root"
              }
            }
          ]
        }
      ]
    },
    {
      "name": "two_level_with_siblings",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/two_level_siblings.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Graph",
          "equals": 1
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Node",
          "equals": 3
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Edge",
          "equals": 2
        },
        {
          "kind": "objects",
          "model": "OUT",
          "type": "Node",
          "idFeature": "name",
          "ids": ["root", "c1", "c2"]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "type": "Edge",
          "sourceFeature": "source.name",
          "targetFeature": "target.name",
          "pairs": [
            ["root", "c1"],
            ["root", "c2"]
          ]
        }
      ]
    },
    {
      "name": "three_level_branching_direction_and_propagation",
      "models": [
        {
          "name": "IN",
          "kind": "emf",
          "role": "source",
          "path": "models/three_level_branching.model",
          "generated": true,
          "metamodelUri": "Tree"
        },
        {
          "name": "OUT",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "Graph"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "OUT",
          "type": "Graph",
          "equals": 1
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Node",
          "equals": 6
        },
        {
          "kind": "count",
          "model": "OUT",
          "type": "Edge",
          "equals": 5
        },
        {
          "kind": "objects",
          "model": "OUT",
          "type": "Node",
          "idFeature": "name",
          "ids": ["A", "B", "C", "D", "E", "F"]
        },
        {
          "kind": "referencePairs",
          "model": "OUT",
          "type": "Edge",
          "sourceFeature": "source.name",
          "targetFeature": "target.name",
          "pairs": [
            ["A", "B"],
            ["A", "C"],
            ["B", "D"],
            ["B", "E"],
            ["C", "F"]
          ]
        },
        {
          "kind": "featureValues",
          "model": "OUT",
          "type": "Node",
          "idFeature": "name",
          "expected": [
            {
              "id": "A",
              "values": {
                "name": "A"
              }
            },
            {
              "id": "B",
              "values": {
                "name": "B"
              }
            },
            {
              "id": "C",
              "values": {
                "name": "C"
              }
            },
            {
              "id": "D",
              "values": {
                "name": "D"
              }
            },
            {
              "id": "E",
              "values": {
                "name": "E"
              }
            },
            {
              "id": "F",
              "values": {
                "name": "F"
              }
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

```xml file=models/two_level_siblings.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="root">
  <children label="c1"/>
  <children label="c2"/>
</Tree:Tree>
```

```xml file=models/three_level_branching.model
<?xml version="1.0" encoding="UTF-8"?>
<Tree:Tree xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:Tree="Tree"
    label="A">
  <children label="B">
    <children label="D"/>
    <children label="E"/>
  </children>
  <children label="C">
    <children label="F"/>
  </children>
</Tree:Tree>
```