```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedMultipleTargetsSemanticTests",
  "transformation": "multiple_targets.etl",
  "metamodels": [
    {"name": "Flowchart", "uri": "flowchart"},
    {"name": "HTML", "uri": "HTML"}
  ],
  "tests": [
    {
      "name": "empty_source_produces_no_target_elements",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 0},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 0},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 0}
      ]
    },
    {
      "name": "single_action_with_outgoing_creates_div_h1_a",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_action_with_outgoing.model",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 1},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Start"]},
        {"kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Next steps", "ahref": "End"}]}
      ]
    },
    {
      "name": "single_action_without_outgoing_is_filtered_by_guard",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_action_without_outgoing.model",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 0},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 0},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 0}
      ]
    },
    {
      "name": "single_decision_with_two_outgoing_creates_title_and_two_links",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/single_decision_two_outgoing.model",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 1},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 2},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Choose"]},
        {"kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Approve", "ahref": "Approve"}, {"value": "Reject", "ahref": "Reject"}]}
      ]
    },
    {
      "name": "mixed_actions_decisions_and_empty_names",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_cases.model",
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
        {"kind": "count", "model": "HTML", "type": "DIV", "expected": 3},
        {"kind": "count", "model": "HTML", "type": "H1", "expected": 3},
        {"kind": "count", "model": "HTML", "type": "A", "expected": 4},
        {"kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["", "Route", "Route"]},
        {"kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Next steps", "ahref": ""}, {"value": "", "ahref": ""}, {"value": "Route", "ahref": "Route"}, {"value": "Route", "ahref": "Route"}]}
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

```xml file=models/single_action_with_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Action xmi:id="a1" name="Start" outgoing="#t1"/>
  <flowchart:Action xmi:id="a2" name="End"/>
  <transitions xmi:id="t1" source="#a1" target="#a2"/>
</xmi:XMI>
```

```xml file=models/single_action_without_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Action xmi:id="a1" name="Lonely"/>
</xmi:XMI>
```

```xml file=models/single_decision_two_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Decision xmi:id="d1" name="Choose" outgoing="#t1 #t2"/>
  <flowchart:Action xmi:id="a1" name="Approve"/>
  <flowchart:Action xmi:id="a2" name="Reject"/>
  <transitions xmi:id="t1" source="#d1" target="#a1"/>
  <transitions xmi:id="t2" source="#d1" target="#a2"/>
</xmi:XMI>
```

```xml file=models/mixed_cases.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Action xmi:id="a1" name="" outgoing="#t1"/>
  <flowchart:Action xmi:id="a2" name="Route" outgoing="#t2"/>
  <flowchart:Action xmi:id="a3" name="Ignored"/>
  <flowchart:Decision xmi:id="d1" name="Route" outgoing="#t3 #t4"/>
  <flowchart:Action xmi:id="a4" name=""/>
  <flowchart:Action xmi:id="a5" name="Route"/>
  <transitions xmi:id="t1" source="#a1" target="#a4"/>
  <transitions xmi:id="t2" source="#a2" target="#a5"/>
  <transitions xmi:id="t3" source="#d1" target="#a4"/>
  <transitions xmi:id="t4" source="#d1" target="#a5"/>
</xmi:XMI>
```