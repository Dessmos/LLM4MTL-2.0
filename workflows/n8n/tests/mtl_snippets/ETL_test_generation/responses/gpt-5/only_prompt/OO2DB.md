```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "OO2DBSemanticCases",
  "transformation": "OO2DB.etl",
  "metamodels": [
    { "name": "DB", "uri": "DB" },
    { "name": "OO", "uri": "OO" },
    { "name": "OO2DB", "uri": "TM" },
    { "name": "Trace", "uri": "SimpleTrace" }
  ],
  "tests": [
    {
      "name": "empty_oo_with_typemap_produces_only_database_and_empty_trace",
      "models": [
        { "name": "OO", "kind": "emf", "role": "source", "path": "models/empty_oo.model", "generated": false, "metamodelUri": "OO" },
        { "name": "OO2DB", "kind": "emf", "role": "source", "path": "models/typemap_minimal.model", "generated": false, "metamodelUri": "TM" },
        { "name": "DB", "kind": "emf", "role": "target", "generated": true, "metamodelUri": "DB" },
        { "name": "Trace", "kind": "emf", "role": "target", "generated": true, "metamodelUri": "SimpleTrace" }
      ],
      "assertions": [
        { "kind": "count", "model": "DB", "type": "Database", "expected": 1 },
        { "kind": "count", "model": "DB", "type": "Table", "expected": 0 },
        { "kind": "count", "model": "DB", "type": "Column", "expected": 0 },
        { "kind": "count", "model": "DB", "type": "ForeignKey", "expected": 0 },
        { "kind": "count", "model": "Trace", "type": "Trace", "expected": 1 },
        { "kind": "count", "model": "Trace", "type": "TraceLink", "expected": 0 }
      ]
    },
    {
      "name": "single_class_single_attribute_reference_and_inheritance",
      "models": [
        { "name": "OO", "kind": "emf", "role": "source", "path": "models/oo_mixed.model", "generated": false, "metamodelUri": "OO" },
        { "name": "OO2DB", "kind": "emf", "role": "source", "path": "models/typemap_full.model", "generated": false, "metamodelUri": "TM" },
        { "name": "DB", "kind": "emf", "role": "target", "generated": true, "metamodelUri": "DB" },
        { "name": "Trace", "kind": "emf", "role": "target", "generated": true, "metamodelUri": "SimpleTrace" }
      ],
      "assertions": [
        { "kind": "count", "model": "DB", "type": "Database", "expected": 1 },
        { "kind": "count", "model": "DB", "type": "Table", "expected": 3 },
        { "kind": "count", "model": "DB", "type": "Column", "expected": 9 },
        { "kind": "count", "model": "DB", "type": "ForeignKey", "expected": 3 },

        { "kind": "featureValues", "model": "DB", "type": "Table", "feature": "name", "expected": ["Person", "Department", "Person_tagsValues"] },
        { "kind": "featureValues", "model": "DB", "type": "Column", "feature": "name", "expected": ["personId", "departmentId", "name", "age", "id", "value", "tagsId", "managerId", "personId"] },
        { "kind": "featureValues", "model": "DB", "type": "ForeignKey", "feature": "name", "expected": ["DepartmentExtendsPerson", "manager", ""] },

        {
          "kind": "objects",
          "model": "DB",
          "type": "Column",
          "features": ["name", "type"],
          "expected": [
            { "name": "personId", "type": "INT" },
            { "name": "departmentId", "type": "INT" },
            { "name": "name", "type": "VARCHAR" },
            { "name": "age", "type": "INT" },
            { "name": "id", "type": "INT" },
            { "name": "value", "type": "VARCHAR" },
            { "name": "tagsId", "type": "INT" },
            { "name": "managerId", "type": "INT" },
            { "name": "personId", "type": "INT" }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "DB",
          "type": "Column",
          "source": "name",
          "target": "table.name",
          "expected": [
            { "source": "personId", "target": "Person" },
            { "source": "departmentId", "target": "Department" },
            { "source": "name", "target": "Person" },
            { "source": "age", "target": "Person" },
            { "source": "id", "target": "Person_tagsValues" },
            { "source": "value", "target": "Person_tagsValues" },
            { "source": "tagsId", "target": "Person" },
            { "source": "managerId", "target": "Department" },
            { "source": "personId", "target": "Department" }
          ]
        },
        {
          "kind": "referencePairs",
          "model": "DB",
          "type": "ForeignKey",
          "source": "child.name",
          "target": "parent.name",
          "expected": [
            { "source": "personId", "target": "personId" },
            { "source": "managerId", "target": "departmentId" },
            { "source": "tagsId", "target": "id" }
          ]
        },

        { "kind": "count", "model": "Trace", "type": "Trace", "expected": 1 },
        { "kind": "count", "model": "Trace", "type": "TraceLink", "expected": 6 },
        { "kind": "featureValues", "model": "Trace", "type": "TraceLink", "feature": "description", "expected": ["Transformed by Class2Table", "Transformed by Class2Table", "Transformed by SingleValuedAttribute2Column", "Transformed by SingleValuedAttribute2Column", "Transformed by MultiValuedAttribute2Table", "Transformed by Reference2ForeignKey"] }
      ]
    }
  ]
}
```

```xml file=models/empty_oo.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:OO="OO"/>
```

```xml file=models/typemap_minimal.model
<?xml version="1.0" encoding="UTF-8"?>
<TM:TypeMap xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:TM="TM">
  <default source="String" target="VARCHAR"/>
</TM:TypeMap>
```

```xml file=models/typemap_full.model
<?xml version="1.0" encoding="UTF-8"?>
<TM:TypeMap xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:TM="TM">
  <mappings source="String" target="VARCHAR"/>
  <mappings source="Integer" target="INT"/>
  <default source="Object" target="VARCHAR"/>
</TM:TypeMap>
```

```xml file=models/oo_mixed.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:OO="OO">
  <OO:Class xmi:id="C1" name="Person">
    <attributes xmi:id="A1" name="name" isMany="false" type="String"/>
    <attributes xmi:id="A2" name="age" isMany="false" type="Integer"/>
    <attributes xmi:id="A3" name="tags" isMany="true" type="String"/>
  </OO:Class>
  <OO:Class xmi:id="C2" name="Department" extends="#C1">
    <references xmi:id="R1" name="manager" type="#C2"/>
  </OO:Class>
</xmi:XMI>
```