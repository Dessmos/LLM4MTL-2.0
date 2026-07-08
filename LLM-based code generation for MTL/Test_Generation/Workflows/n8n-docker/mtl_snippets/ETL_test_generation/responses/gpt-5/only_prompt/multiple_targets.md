```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "MultipleTargetsSemanticTests",
  "transformation": "multiple_targets.etl",
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
      "name": "empty_source_produces_no_targets",
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
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 0 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 0 },
        { "kind": "count", "model": "HTML", "type": "A", "expected": 0 }
      ]
    },
    {
      "name": "single_action_without_outgoing_is_filtered_by_guard",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/action_no_outgoing.model",
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
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 0 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 0 },
        { "kind": "count", "model": "HTML", "type": "A", "expected": 0 }
      ]
    },
    {
      "name": "single_action_with_outgoing_produces_div_h1_a",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/action_with_outgoing.model",
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
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "A", "expected": 1 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Start"] },
        { "kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Next steps", "ahref": "End"}] },
        { "kind": "referencePairs", "model": "HTML", "type": "DIV", "source": "children.value", "target": "children.eClass().name", "expected": [{"source": "Start", "target": "H1"}, {"source": "Next steps", "target": "A"}] }
      ]
    },
    {
      "name": "single_decision_with_two_outgoing_produces_title_and_two_links",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/decision_two_outgoing.model",
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
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 1 },
        { "kind": "count", "model": "HTML", "type": "A", "expected": 2 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["Choose"] },
        { "kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Approve", "ahref": "Approve"}, {"value": "Reject", "ahref": "Reject"}] },
        { "kind": "pathValues", "model": "HTML", "type": "DIV", "path": "children.value", "expected": ["Choose", "Approve", "Reject"] }
      ]
    },
    {
      "name": "mixed_actions_and_decision_with_empty_and_duplicate_names",
      "models": [
        {
          "name": "Flowchart",
          "kind": "emf",
          "role": "source",
          "path": "models/mixed_duplicates_empty.model",
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
        { "kind": "count", "model": "HTML", "type": "DIV", "expected": 3 },
        { "kind": "count", "model": "HTML", "type": "H1", "expected": 3 },
        { "kind": "count", "model": "HTML", "type": "A", "expected": 4 },
        { "kind": "featureValues", "model": "HTML", "type": "H1", "feature": "value", "expected": ["A1", "", "D"] },
        { "kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Next steps", "ahref": ""}, {"value": "Next steps", "ahref": "Dup"}, {"value": "Dup", "ahref": "Dup"}, {"value": "Dup", "ahref": "Dup"}] }
      ]
    }
  ]
}
```

```xml file=models/empty_flowchart.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart"/>
```

```xml file=models/action_no_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart">
  <nodes xsi:type="flowchart:Action" name="Get up"/>
</flowchart:Flowchart>
```

```xml file=models/action_with_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart">
  <nodes xsi:type="flowchart:Action" name="Start" outgoing="//@nodes.0/@outgoing.0"/>
  <nodes xsi:type="flowchart:Action" name="End" incoming="//@nodes.0/@outgoing.0"/>
</flowchart:Flowchart>
```

```xml file=models/decision_two_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart">
  <nodes xsi:type="flowchart:Decision" name="Choose" outgoing="//@nodes.0/@outgoing.0 //@nodes.0/@outgoing.1"/>
  <nodes xsi:type="flowchart:Action" name="Approve" incoming="//@nodes.0/@outgoing.0"/>
  <nodes xsi:type="flowchart:Action" name="Reject" incoming="//@nodes.0/@outgoing.1"/>
</flowchart:Flowchart>
```

```xml file=models/mixed_duplicates_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<flowchart:Flowchart xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:flowchart="flowchart">
  <nodes xsi:type="flowchart:Action" name="A1" outgoing="//@nodes.0/@outgoing.0"/>
  <nodes xsi:type="flowchart:Action" name="" incoming="//@nodes.0/@outgoing.0"/>
  <nodes xsi:type="flowchart:Action" name="" outgoing="//@nodes.2/@outgoing.0"/>
  <nodes xsi:type="flowchart:Action" name="Dup" incoming="//@nodes.2/@outgoing.0 //@nodes.3/@outgoing.0 //@nodes.3/@outgoing.1"/>
  <nodes xsi:type="flowchart:Decision" name="D" outgoing="//@nodes.3/@outgoing.0 //@nodes.3/@outgoing.1"/>
</flowchart:Flowchart>
```