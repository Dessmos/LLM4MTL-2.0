```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedGreedyEtlSemanticTests",
  "transformation": "greedy.etl",
  "metamodels": [
    {"name": "Flowchart", "uri": "flowchart"},
    {"name": "HTML", "uri": "HTML"}
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
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 0},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": []}
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
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 1},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Start"]},
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            {"value": "Start"}
          ]
        }
      ]
    },
    {
      "name": "multiple_named_elements_map_one_to_one_preserving_duplicates_and_empty",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/multiple_named_elements.model",
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
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 4},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Alpha", "Alpha", "", "Omega"]},
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            {"value": "Alpha"},
            {"value": "Alpha"},
            {"value": ""},
            {"value": "Omega"}
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
</xmi:XMI>
```

```xml file=models/single_named_element.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:NamedElement name="Start"/>
</xmi:XMI>
```

```xml file=models/multiple_named_elements.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:NamedElement name="Alpha"/>
  <flowchart:NamedElement name="Alpha"/>
  <flowchart:NamedElement name=""/>
  <flowchart:NamedElement name="Omega"/>
</xmi:XMI>
```