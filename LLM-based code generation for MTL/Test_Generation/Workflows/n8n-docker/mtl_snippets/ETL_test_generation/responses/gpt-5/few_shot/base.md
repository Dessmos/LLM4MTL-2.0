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
          "path": "models/empty_source.model",
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
      "name": "one_instance_per_mapped_type_creates_four_h1",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/one_per_type.model",
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
            "MainFlow",
            "DoWork",
            "CheckCondition",
            "t1"
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
              "value": "MainFlow"
            },
            {
              "value": "DoWork"
            },
            {
              "value": "CheckCondition"
            },
            {
              "value": "t1"
            }
          ]
        }
      ]
    },
    {
      "name": "mixed_instances_across_types_create_exact_h1_values",
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
          "generated": false,
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
          "expected": [
            "FlowA",
            "FlowB",
            "ActionA",
            "ActionB",
            "DecisionA",
            "TransitionA",
            "TransitionB"
          ]
        }
      ]
    },
    {
      "name": "duplicate_and_empty_names_are_preserved_in_h1_values",
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
          "expected": 6
        },
        {
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "",
            "same",
            "same",
            "",
            "same",
            ""
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
              "value": ""
            },
            {
              "value": "same"
            },
            {
              "value": "same"
            },
            {
              "value": ""
            },
            {
              "value": "same"
            },
            {
              "value": ""
            }
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_source.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
</xmi:XMI>
```

```xml file=models/one_per_type.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="MainFlow"/>
  <flowchart:Action name="DoWork"/>
  <flowchart:Decision name="CheckCondition"/>
  <flowchart:Transition name="t1"/>
</xmi:XMI>
```

```xml file=models/mixed_instances.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name="FlowA"/>
  <flowchart:Flowchart name="FlowB"/>
  <flowchart:Action name="ActionA"/>
  <flowchart:Action name="ActionB"/>
  <flowchart:Decision name="DecisionA"/>
  <flowchart:Transition name="TransitionA"/>
  <flowchart:Transition name="TransitionB"/>
</xmi:XMI>
```

```xml file=models/duplicate_empty_names.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Flowchart name=""/>
  <flowchart:Action name="same"/>
  <flowchart:Decision name="same"/>
  <flowchart:Transition name=""/>
  <flowchart:Action name="same"/>
  <flowchart:Flowchart name=""/>
</xmi:XMI>
```