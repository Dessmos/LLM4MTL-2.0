```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GreedyEtlSemanticTests",
  "transformation": "greedy.etl",
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
      "name": "empty_source_produces_no_h1",
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
          "type": "H1",
          "expected": 0
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": []
        }
      ]
    },
    {
      "name": "single_named_element_maps_to_single_h1",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_named_element.model",
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
          "type": "H1",
          "expected": 1
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
              "value": "Start"
            }
          ]
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Start"
          ]
        }
      ]
    },
    {
      "name": "multiple_named_elements_preserve_values_including_duplicates_and_empty",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_named_elements.model",
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
            "A",
            "",
            "B"
          ]
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
              "value": "A"
            },
            {
              "value": "A"
            },
            {
              "value": ""
            },
            {
              "value": "B"
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:NamedElement xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name=""/>
```

```xml file=models/single_named_element.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:NamedElement xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name="Start"/>
```

```xml file=models/multiple_named_elements.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:NamedElement xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name="A"/>
```