```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "equivalentSemanticCases",
  "transformation": "equivalent.etl",
  "metamodels": [
    { "name": "Flowchart", "uri": "flowchart" },
    { "name": "HTML", "uri": "HTML" }
  ],
  "tests": [
    {
      "name": "empty_flowchart_produces_one_empty_div",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/empty_flowchart.model",
          "generated": false,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 0 },
        { "kind": "pathValues", "model": "HTML", "type": "DIV", "path": "children.value", "expected": [] }
      ]
    },
    {
      "name": "single_transition_maps_to_single_h1_child",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_transition.model",
          "generated": false,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 1 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Start"] },
        { "kind": "pathValues", "model": "HTML", "type": "DIV", "path": "children.value", "expected": ["Start"] }
      ]
    },
    {
      "name": "multiple_transitions_preserve_names_in_children",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_transitions.model",
          "generated": false,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 3 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["A", "B", "C"] },
        { "kind": "pathValues", "model": "HTML", "type": "DIV", "path": "children.value", "expected": ["A", "B", "C"] }
      ]
    },
    {
      "name": "duplicate_and_empty_transition_names_are_preserved",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/duplicate_empty_names.model",
          "generated": false,
          "metamodelUri": "flowchart"
        },
        {
          "name": "HTML",
          "kind": "emf",
          "role": "target",
          "generated": true,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 3 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["", "Dup", "Dup"] },
        { "kind": "pathValues", "model": "HTML", "type": "DIV", "path": "children.value", "expected": ["", "Dup", "Dup"] }
      ]
    }
  ]
}
```

```xml file=models/empty_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"/>
```

```xml file=models/single_transition.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    transitions="//@transitions.0">
  <transitions name="Start"/>
</flowchart:Flowchart>
```

```xml file=models/multiple_transitions.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    transitions="//@transitions.0 //@transitions.1 //@transitions.2">
  <transitions name="A"/>
  <transitions name="B"/>
  <transitions name="C"/>
</flowchart:Flowchart>
```

```xml file=models/duplicate_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    transitions="//@transitions.0 //@transitions.1 //@transitions.2">
  <transitions name=""/>
  <transitions name="Dup"/>
  <transitions name="Dup"/>
</flowchart:Flowchart>
```