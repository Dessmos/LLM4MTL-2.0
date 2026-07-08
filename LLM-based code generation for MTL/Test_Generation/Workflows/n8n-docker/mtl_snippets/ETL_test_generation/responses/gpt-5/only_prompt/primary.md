```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "PrimaryEtlSemanticCases",
  "transformation": "primary.etl",
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
      "name": "empty_flowchart_produces_empty_div_only",
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
          "kind": "count",
          "model": "HTML",
          "type": "A",
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
      "name": "single_transition_creates_one_div_one_h1_and_two_links",
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
          "kind": "count",
          "model": "HTML",
          "type": "A",
          "expected": 2
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["T1"]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": ["value", "ahref"],
          "expected": [
            {
              "value": "Start",
              "ahref": "#Start"
            },
            {
              "value": "T1",
              "ahref": "#End"
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["T1"]
        }
      ]
    },
    {
      "name": "multiple_transitions_duplicate_and_empty_names",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_transitions_duplicates_empty.model",
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
          "kind": "count",
          "model": "HTML",
          "type": "A",
          "expected": 6
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["Alpha", "Alpha", ""]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": ["value", "ahref"],
          "expected": [
            {
              "value": "S1",
              "ahref": "#M"
            },
            {
              "value": "Alpha",
              "ahref": "#S2"
            },
            {
              "value": "M",
              "ahref": "#S1"
            },
            {
              "value": "Alpha",
              "ahref": "#S1"
            },
            {
              "value": "",
              "ahref": "#"
            },
            {
              "value": "",
              "ahref": "#"
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": ["Alpha", "Alpha", ""]
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

```xml file=models/single_transition.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <transitions name="T1">
    <source name="Start"/>
    <target name="End"/>
  </transitions>
</flowchart:Flowchart>
```

```xml file=models/multiple_transitions_duplicates_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <transitions name="Alpha">
    <source name="S1"/>
    <target name="M"/>
  </transitions>
  <transitions name="Alpha">
    <source name="M"/>
    <target name="S1"/>
  </transitions>
  <transitions name="">
    <source name=""/>
    <target name=""/>
  </transitions>
</flowchart:Flowchart>
```