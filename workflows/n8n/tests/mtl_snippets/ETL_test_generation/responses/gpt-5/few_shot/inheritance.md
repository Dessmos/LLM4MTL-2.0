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
      "name": "single_flowchart_maps_to_flowchart_prefixed_h1",
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
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Flowchart Main"
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
              "value": "Flowchart Main"
            }
          ]
        }
      ]
    },
    {
      "name": "single_subflow_uses_extended_rule_and_overrides_value",
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
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Subflow Flowchart Child"
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
              "value": "Subflow Flowchart Child"
            }
          ]
        }
      ]
    },
    {
      "name": "mixed_flowchart_and_subflow_instances_map_each_once",
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
          "expected": 3
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Flowchart Top",
            "Subflow Flowchart NestedA",
            "Subflow Flowchart NestedB"
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
              "value": "Flowchart Top"
            },
            {
              "value": "Subflow Flowchart NestedA"
            },
            {
              "value": "Subflow Flowchart NestedB"
            }
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_preserve_exact_string_concatenation",
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
              "value": "Flowchart "
            },
            {
              "value": "Flowchart Dup"
            },
            {
              "value": "Subflow Flowchart "
            },
            {
              "value": "Subflow Flowchart Dup"
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
  <flowchart:Flowchart name="Top"/>
  <flowchart:Subflow name="NestedA"/>
  <flowchart:Subflow name="NestedB"/>
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