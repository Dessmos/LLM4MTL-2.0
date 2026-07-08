```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedPrimaryEtlSemanticTests",
  "transformation": "primary.etl",
  "metamodels": [
    {"name": "Flowchart", "uri": "flowchart"},
    {"name": "HTML", "uri": "HTML"}
  ],
  "tests": [
    {
      "name": "empty_flowchart_produces_only_div_without_children",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 0},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 0},
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
      "name": "single_transition_creates_heading_and_two_links_with_expected_values",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 2},
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            {"value": "Go"}
          ]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": ["value", "ahref"],
          "expected": [
            {"value": "Start", "ahref": "#Start"},
            {"value": "Go", "ahref": "#End"}
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["Go"]
        }
      ]
    },
    {
      "name": "multiple_transitions_with_duplicate_and_empty_names_preserve_exact_outputs",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multi_transition_duplicates_empty.model",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 3},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 6},
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["", "T", "T"]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": ["value", "ahref"],
          "expected": [
            {"value": "N1", "ahref": "#N1"},
            {"value": "", "ahref": "#N2"},
            {"value": "N1", "ahref": "#N1"},
            {"value": "T", "ahref": "#N3"},
            {"value": "N2", "ahref": "#N2"},
            {"value": "T", "ahref": "#N1"}
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["", "T", "T"]
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
    xmlns:flowchart="flowchart">
  <transitions name="Go" source="#//@transitions.0" target="#//@transitions.1"/>
  <transitions name="Start"/>
  <transitions name="End"/>
</flowchart:Flowchart>
```

```xml file=models/multi_transition_duplicates_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <transitions name="" source="#//@transitions.1" target="#//@transitions.2"/>
  <transitions name="N1"/>
  <transitions name="N2"/>
  <transitions name="T" source="#//@transitions.1" target="#//@transitions.4"/>
  <transitions name="N3"/>
  <transitions name="T" source="#//@transitions.2" target="#//@transitions.1"/>
</flowchart:Flowchart>
```