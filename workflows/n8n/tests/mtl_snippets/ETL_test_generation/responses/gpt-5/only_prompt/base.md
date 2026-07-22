```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "BaseEtlSemanticTests",
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
      "name": "empty_flowchart_model_produces_no_h1",
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
          "expected": ["StartFlow", "ActA", "DecideB", "TransC"]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            { "value": "StartFlow" },
            { "value": "ActA" },
            { "value": "DecideB" },
            { "value": "TransC" }
          ]
        }
      ]
    },
    {
      "name": "mixed_instances_across_types_exact_cardinality",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_instances.model",
          "generated": true,
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
          "expected": 7
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["MainFlow", "AuxFlow", "A1", "A2", "D1", "T1", "T2"]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_are_preserved",
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
          "generated": true,
          "metamodelUri": "HTML"
        }
      ],
      "assertions": [
        {
          "kind": "count",
          "model": "HTML",
          "type": "H1",
          "expected": 5
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": ["", "", "Dup", "Dup", "UniqueT"]
        },
        {
          "kind": "objects",
          "model": "HTML",
          "type": "H1",
          "features": ["value"],
          "expected": [
            { "value": "" },
            { "value": "" },
            { "value": "Dup" },
            { "value": "Dup" },
            { "value": "UniqueT" }
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
  <flowchart:Flowchart name="StartFlow"/>
  <flowchart:Action name="ActA"/>
  <flowchart:Decision name="DecideB"/>
  <flowchart:Transition name="TransC"/>
</xmi:XMI>
```

```xml file=models/mixed_instances.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="MainFlow"/>
  <flowchart:Flowchart name="AuxFlow"/>
  <flowchart:Action name="A1"/>
  <flowchart:Action name="A2"/>
  <flowchart:Decision name="D1"/>
  <flowchart:Transition name="T1"/>
  <flowchart:Transition name="T2"/>
</xmi:XMI>
```

```xml file=models/duplicate_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name=""/>
  <flowchart:Action name=""/>
  <flowchart:Decision name="Dup"/>
  <flowchart:Transition name="Dup"/>
  <flowchart:Transition name="UniqueT"/>
</xmi:XMI>
```