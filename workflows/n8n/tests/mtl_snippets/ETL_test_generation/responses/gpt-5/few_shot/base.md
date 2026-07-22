```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedBaseEtlSemanticTests",
  "transformation": "base.etl",
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
      "name": "one_instance_per_mapped_source_type",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/one_each_type.model",
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
          "type": "H1",
          "expected": 4
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["MainFlow", "DoTask", "CheckCondition", "toNext"]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            {"value": "MainFlow"},
            {"value": "DoTask"},
            {"value": "CheckCondition"},
            {"value": "toNext"}
          ]
        }
      ]
    },
    {
      "name": "mixed_instances_include_duplicates_and_empty_names",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_duplicates_empty.model",
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
          "type": "H1",
          "expected": 8
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["", "A", "A", "", "D", "D", "T", ""]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            {"value": ""},
            {"value": "A"},
            {"value": "A"},
            {"value": ""},
            {"value": "D"},
            {"value": "D"},
            {"value": "T"},
            {"value": ""}
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

```xml file=models/one_each_type.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="MainFlow"/>
  <flowchart:Action name="DoTask"/>
  <flowchart:Decision name="CheckCondition"/>
  <flowchart:Transition name="toNext"/>
</xmi:XMI>
```

```xml file=models/mixed_duplicates_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name=""/>
  <flowchart:Action name="A"/>
  <flowchart:Action name="A"/>
  <flowchart:Decision name=""/>
  <flowchart:Decision name="D"/>
  <flowchart:Transition name="D"/>
  <flowchart:Transition name="T"/>
  <flowchart:Flowchart name=""/>
</xmi:XMI>
```