```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "inheritanceSemanticCases",
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
      "name": "emptyFlowchartNameProducesSingleH1",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/empty_name_flowchart.model",
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
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Flowchart "
          ]
        }
      ]
    },
    {
      "name": "singleSubflowUsesExtendedRuleValue",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_subflow.model",
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
          "kind": "featureValues",
          "model": "HTML",
          "type": "H1",
          "feature": "value",
          "expected": [
            "Subflow Flowchart S1"
          ]
        }
      ]
    },
    {
      "name": "mixedFlowchartAndSubflowWithDuplicateAndEmptyNames",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_flowchart_subflow_duplicates.model",
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
            "Flowchart Common",
            "Subflow Flowchart Common",
            "Subflow Flowchart ",
            "Flowchart "
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_name_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name=""/>
```

```xml file=models/single_subflow.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Subflow xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart"
    name="S1"/>
```

```xml file=models/mixed_flowchart_subflow_duplicates.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"
    name="Common">
  <children xsi:type="flowchart:Subflow" name="Common"/>
  <children xsi:type="flowchart:Subflow" name=""/>
  <children xsi:type="flowchart:Flowchart" name=""/>
</flowchart:Flowchart>
```