```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedEquivalentEtlSemanticTests",
  "transformation": "equivalent.etl",
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
      "name": "empty_flowchart_produces_one_div_with_no_children_and_no_h1",
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
      "name": "single_flowchart_with_one_transition_produces_div_and_one_h1",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_transition_flowchart.model",
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
          "expected": 1
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Start"
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": [
            "Start"
          ]
        }
      ]
    },
    {
      "name": "single_flowchart_with_multiple_transitions_including_duplicates_and_empty_name",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_transitions_flowchart.model",
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
            "A",
            "",
            "A",
            "B"
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": [
            "A",
            "",
            "A",
            "B"
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
    xmlns:flowchart="flowchart"/>
```

```xml file=models/single_transition_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    transitions="//@transitions.0">
  <transitions name="Start"/>
</flowchart:Flowchart>
```

```xml file=models/multiple_transitions_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    transitions="//@transitions.0 //@transitions.1 //@transitions.2 //@transitions.3">
  <transitions name="A"/>
  <transitions name=""/>
  <transitions name="A"/>
  <transitions name="B"/>
</flowchart:Flowchart>
```