```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedPrimaryEtlSemanticTests",
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
      "name": "empty_flowchart_produces_only_empty_div",
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
      "name": "single_transition_creates_heading_and_two_links",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_transition.model",
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
          "kind": "count",
          "model": "HTML",
          "type": "A",
          "expected": 2
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": [
            "value"
          ],
          "expected": [
            {
              "value": "T1"
            }
          ]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": [
            "value",
            "ahref"
          ],
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
          "expected": [
            "T1"
          ]
        }
      ]
    },
    {
      "name": "multiple_transitions_with_duplicate_and_empty_names",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_transitions_duplicates_empty.model",
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
          "expected": [
            "Go",
            "Go",
            ""
          ]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "A",
          "features": [
            "value",
            "ahref"
          ],
          "expected": [
            {
              "value": "S",
              "ahref": "#S"
            },
            {
              "value": "Go",
              "ahref": "#M"
            },
            {
              "value": "M",
              "ahref": "#M"
            },
            {
              "value": "Go",
              "ahref": "#E"
            },
            {
              "value": "E",
              "ahref": "#E"
            },
            {
              "value": "",
              "ahref": "#S"
            }
          ]
        },
        {
          "kind": "pathValues",
          "model": "HTML",
          "type": "DIV",
          "path": "children.value",
          "expected": [
            "Go",
            "Go",
            ""
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
  <transitions name="Go">
    <source name="S"/>
    <target name="M"/>
  </transitions>
  <transitions name="Go">
    <source name="M"/>
    <target name="E"/>
  </transitions>
  <transitions name="">
    <source name="E"/>
    <target name="S"/>
  </transitions>
</flowchart:Flowchart>
```