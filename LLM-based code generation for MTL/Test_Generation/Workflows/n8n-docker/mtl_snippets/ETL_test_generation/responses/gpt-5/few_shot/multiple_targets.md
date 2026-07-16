```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedMultipleTargetsSemanticTests",
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
      "name": "empty_source_produces_no_html_elements",
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
        {"kind": "objects", "model": "HTML", "type": "H1", "features": ["value"], "expected": [{"value": "Start"}]},
        {"kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "Next steps", "ahref": "Next"}]},
        {"kind": "referencePairs", "model": "HTML", "type": "DIV", "source": "children.value", "target": "children.ahref", "expected": [{"source": "Start", "target": null}, {"source": "Next steps", "target": "Next"}]}
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
        {"kind": "objects", "model": "HTML", "type": "H1", "features": ["value"], "expected": [{"value": "Choose"}]},
        {"kind": "objects", "model": "HTML", "type": "A", "features": ["value", "ahref"], "expected": [{"value": "PathA", "ahref": "PathA"}, {"value": "PathB", "ahref": "PathB"}]}
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
  <flowchart:Action name="Start" outgoing="//@transitions.0"/>
  <flowchart:Action name="Next"/>
  <flowchart:Transition source="//@Action.0" target="//@Action.1"/>
</xmi:XMI>
```

```xml file=models/single_action_without_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Action name="Get up"/>
</xmi:XMI>
```

```xml file=models/single_decision_two_outgoing.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:flowchart="flowchart">
  <flowchart:Decision name="Choose" outgoing="//@transitions.0 //@transitions.1"/>
  <flowchart:Action name="PathA"/>
  <flowchart:Action name="PathB"/>
  <flowchart:Transition source="//@Decision.0" target="//@Action.0"/>
  <flowchart:Transition source="//@Decision.0" target="//@Action.1"/>
</xmi:XMI>
```