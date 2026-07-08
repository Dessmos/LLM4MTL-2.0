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
      "name": "empty_source_flowchart_creates_single_empty_div",
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
      "name": "one_action_one_decision_and_transition_create_two_h1_children",
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
          "expected": [
            "Act",
            "Dec"
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": [
            "Act",
            "Dec"
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_are_preserved_in_h1_values",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/duplicate_empty_names.model",
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
          "expected": 4
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "",
            "",
            "Same",
            "Same"
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": [
            "",
            "",
            "Same",
            "Same"
          ]
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
  <nodes xsi:type="flowchart:Action" name="Act"/>
  <nodes xsi:type="flowchart:Decision" name="Dec"/>
  <transitions name="IgnoredTransition"/>
</flowchart:Flowchart>
```

```xml file=models/duplicate_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    name="DupEmptyFlow">
  <nodes xsi:type="flowchart:Action" name=""/>
  <nodes xsi:type="flowchart:Decision" name=""/>
  <nodes xsi:type="flowchart:Action" name="Same"/>
  <nodes xsi:type="flowchart:Decision" name="Same"/>
</flowchart:Flowchart>
```