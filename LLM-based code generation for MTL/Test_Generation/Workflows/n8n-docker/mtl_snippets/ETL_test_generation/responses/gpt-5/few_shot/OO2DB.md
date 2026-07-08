```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedOO2DBSemanticTests",
  "transformation": "OO2DB.etl",
  "metamodels": [
    {"name": "DB", "uri": "DB"},
    {"name": "OO", "uri": "OO"},
    {"name": "OO2DB", "uri": "TM"},
    {"name": "Trace", "uri": "SimpleTrace"}
  ],
  "tests": [
    {
      "name": "empty_oo_with_typemap_creates_only_database_and_trace",
      "models": [
        {"name": "OO", "kind": "emf", "role": "source", "path": "models/empty_oo.model", "generated": true, "metamodelUri": "OO"},
        {"name": "OO2DB", "kind": "emf", "role": "source", "path": "models/typemap_basic.model", "generated": true, "metamodelUri": "TM"},
        {"name": "DB", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "DB"},
        {"name": "Trace", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "SimpleTrace"}
      ],
      "assertions": [
        {"kind": "count", "model": "DB", "type": "Database", "expected": 1},
        {"kind": "count", "model": "DB", "type": "Table", "expected": 0},
        {"kind": "count", "model": "DB", "type": "Column", "expected": 0},
        {"kind": "count", "model": "DB", "type": "ForeignKey", "expected": 0},
        {"kind": "count", "model": "Trace", "type": "Trace", "expected": 1},
        {"kind": "count", "model": "Trace", "type": "TraceLink", "expected": 0}
      ]
    },
    {
      "name": "single_class_single_attribute_and_reference_mapping",
      "models": [
        {"name": "OO", "kind": "emf", "role": "source", "path": "models/single_class_attr_ref.model", "generated": true, "metamodelUri": "OO"},
        {"name": "OO2DB", "kind": "emf", "role": "source", "path": "models/typemap_basic.model", "generated": true, "metamodelUri": "TM"},
        {"name": "DB", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "DB"},
        {"name": "Trace", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "SimpleTrace"}
      ],
      "assertions": [
        {"kind": "count", "model": "DB", "type": "Database", "expected": 1},
        {"kind": "count", "model": "DB", "type": "Table", "expected": 2},
        {"kind": "count", "model": "DB", "type": "Column", "expected": 5},
        {"kind": "count", "model": "DB", "type": "ForeignKey", "expected": 2},
        {
          "kind": "objects",
          "model": "DB",
          "type": "Table",
          "features": ["name"],
          "expected": [
            {"name": "Person"},
            {"name": "Address"}
          ]
        },
        {
          "kind": "objects",
          "model": "DB",
          "type": "Column",
          "features": ["name", "type"],
          "expected": [
            {"name": "personId", "type": "INT"},
            {"name": "name", "type": "VARCHAR"},
            {"name": "addressId", "type": "INT"},
            {"name": "addressId", "type": "INT"},
            {"name": "street", "type": "VARCHAR"}
          ]
        },
        {
          "kind": "referencePairs",
          "model": "DB",
          "type": "ForeignKey",
          "source": "child.name",
          "target": "parent.name",
          "expected": [
            {"source": "addressId", "target": "addressId"},
            {"source": "addressId", "target": "personId"}
          ]
        },
        {
          "kind": "featureValues",
          "model": "DB",
          "type": "ForeignKey",
          "feature": "name",
          "expected": ["owner", "PersonExtendsAddress"]
        },
        {"kind": "count", "model": "Trace", "type": "Trace", "expected": 1},
        {"kind": "count", "model": "Trace", "type": "TraceLink", "expected": 5},
        {
          "kind": "featureValues",
          "model": "Trace",
          "type": "TraceLink",
          "feature": "description",
          "expected": [
            "Transformed by Class2Table",
            "Transformed by Class2Table",
            "Transformed by SingleValuedAttribute2Column",
            "Transformed by SingleValuedAttribute2Column",
            "Transformed by Reference2ForeignKey"
          ]
        }
      ]
    },
    {
      "name": "multi_valued_attribute_creates_values_table_and_fk",
      "models": [
        {"name": "OO", "kind": "emf", "role": "source", "path": "models/multivalued_attribute.model", "generated": true, "metamodelUri": "OO"},
        {"name": "OO2DB", "kind": "emf", "role": "source", "path": "models/typemap_basic.model", "generated": true, "metamodelUri": "TM"},
        {"name": "DB", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "DB"},
        {"name": "Trace", "kind": "emf", "role": "target", "generated": false, "metamodelUri": "SimpleTrace"}
      ],
      "assertions": [
        {"kind": "count", "model": "DB", "type": "Database", "expected": 1},
        {"kind": "count", "model": "DB", "type": "Table", "expected": 2},
        {"kind": "count", "model": "DB", "type": "Column", "expected": 4},
        {"kind": "count", "model": "DB", "type": "ForeignKey", "expected": 1},
        {
          "kind": "featureValues",
          "model": "DB",
          "type": "Table",
          "feature": "name",
          "expected": ["Book", "Book_TagsValues"]
        },
        {
          "kind": "objects",
          "model": "DB",
          "type": "Column",
          "features": ["name", "type"],
          "expected": [
            {"name": "bookId", "type": "INT"},
            {"name": "id", "type": "INT"},
            {"name": "value", "type": "VARCHAR"},
            {"name": "tagsId", "type": "INT"}
          ]
        },
        {
          "kind": "referencePairs",
          "model": "DB",
          "type": "ForeignKey",
          "source": "child.name",
          "target": "parent.name",
          "expected": [
            {"source": "tagsId", "target": "id"}
          ]
        },
        {"kind": "count", "model": "Trace", "type": "TraceLink", "expected": 2},
        {
          "kind": "featureValues",
          "model": "Trace",
          "type": "TraceLink",
          "feature": "description",
          "expected": [
            "Transformed by Class2Table",
            "Transformed by MultiValuedAttribute2Table"
          ]
        }
      ]
    }
  ]
}
```

```xml file=models/empty_oo.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:OO="OO">
</xmi:XMI>
```

```xml file=models/typemap_basic.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:TM="TM">
  <TM:TypeMap default="//@TM:TypeMapping.0"/>
  <TM:TypeMapping source="String" target="VARCHAR"/>
  <TM:TypeMapping source="Integer" target="INT"/>
</xmi:XMI>
```

```xml file=models/single_class_attr_ref.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:OO="OO">
  <OO:Class name="Person" extends="//@OO:Class.1"/>
  <OO:Class name="Address"/>
  <OO:Attribute name="name" isMany="false" owner="//@OO:Class.0" type="String"/>
  <OO:Attribute name="street" isMany="false" owner="//@OO:Class.1" type="String"/>
  <OO:Reference name="owner" owner="//@OO:Class.1" type="//@OO:Class.0"/>
</xmi:XMI>
```

```xml file=models/multivalued_attribute.model
<?xml version="1.0" encoding="UTF-8"?>
<xmi:XMI xmi:version="2.0"
    xmlns:xmi="http://www.omg.org/XMI"
    xmlns:OO="OO">
  <OO:Class name="Book"/>
  <OO:Attribute name="tags" isMany="true" owner="//@OO:Class.0" type="String"/>
</xmi:XMI>
```