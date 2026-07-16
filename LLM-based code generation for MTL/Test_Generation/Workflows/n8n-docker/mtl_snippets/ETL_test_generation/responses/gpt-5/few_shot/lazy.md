```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedLazyEtlSemanticTests",
  "transformation": "lazy.etl",
  "metamodels": [
    {
      "name": "Flowchart",
      "uri": "flowchart"
    },
    {
      "name": "HTML",
      "uri": "HTML"
    }
  ],
  "tests": [
    {
      "name": "empty_flowchart_produces_one_div_with_no_h1_children",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/empty_flowchart.model",
          "generated": true,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "HTML",
          "type": "DIV",
          "expected": 1
        },
        {
          "kind": "count",
          "model": "HTML",
          "type": "H1",
          "expected": 0
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": []
        }
      ]
    },
    {
      "name": "action_decision_and_transition_nodes_map_only_action_and_decision_to_h1",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_nodes_with_transition.model",
          "generated": true,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "HTML",
          "type": "DIV",
          "expected": 1
        },
        {
          "kind": "count",
          "model": "HTML",
          "type": "H1",
          "expected": 2
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["A1", "D1"]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["A1", "D1"]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_are_preserved_in_created_h1_values",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/duplicate_and_empty_names.model",
          "generated": true,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": false,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "HTML",
          "type": "DIV",
          "expected": 1
        },
        {
          "kind": "count",
          "model": "HTML",
          "type": "H1",
          "expected": 3
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["", "dup", "dup"]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["", "dup", "dup"]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name="EmptyFlow"/>
```

```xml file=models/mixed_nodes_with_transition.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    name="MixedFlow">
  <nodes xsi:type="flowchart:Action" name="A1"/>
  <nodes xsi:type="flowchart:Decision" name="D1"/>
  <nodes xsi:type="flowchart:Transition" name="T1"/>
</flowchart:Flowchart>
```

```xml file=models/duplicate_and_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    name="DupAndEmptyFlow">
  <nodes xsi:type="flowchart:Action" name=""/>
  <nodes xsi:type="flowchart:Action" name="dup"/>
  <nodes xsi:type="flowchart:Decision" name="dup"/>
</flowchart:Flowchart>
```