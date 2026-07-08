```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedInheritanceEtlSemanticTests",
  "transformation": "inheritance.etl",
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
      "name": "single_flowchart_maps_with_flowchart_prefix",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_flowchart.model",
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
              "value": "Flowchart Main"
            }
          ]
        }
      ]
    },
    {
      "name": "single_subflow_uses_extended_rule_value",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_subflow.model",
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
              "value": "Subflow Flowchart Child"
            }
          ]
        }
      ]
    },
    {
      "name": "mixed_flowchart_and_subflow_instances_map_all",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_flowchart_subflow.model",
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
          "expected": [
            "Flowchart Alpha",
            "Flowchart Beta",
            "Subflow Flowchart AlphaSub",
            "Subflow Flowchart BetaSub"
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_preserve_exact_output_values",
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
          "type": "H1",
          "expected": 4
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Flowchart ",
            "Flowchart Dup",
            "Subflow Flowchart ",
            "Subflow Flowchart Dup"
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

```xml file=models/single_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="Main"/>
</xmi:XMI>
```

```xml file=models/single_subflow.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Subflow name="Child"/>
</xmi:XMI>
```

```xml file=models/mixed_flowchart_subflow.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="Alpha"/>
  <flowchart:Flowchart name="Beta"/>
  <flowchart:Subflow name="AlphaSub"/>
  <flowchart:Subflow name="BetaSub"/>
</xmi:XMI>
```

```xml file=models/duplicate_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name=""/>
  <flowchart:Flowchart name="Dup"/>
  <flowchart:Subflow name=""/>
  <flowchart:Subflow name="Dup"/>
</xmi:XMI>
```