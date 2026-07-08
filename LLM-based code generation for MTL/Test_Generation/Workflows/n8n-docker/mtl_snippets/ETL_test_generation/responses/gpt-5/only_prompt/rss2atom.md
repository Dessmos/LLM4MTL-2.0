```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "Rss2AtomSemanticTests",
  "transformation": "rss2atom.etl",
  "metamodels": [
    { "name": "RSS" },
    { "name": "Atom" }
  ],
  "tests": [
    {
      "name": "minimal_rss_no_items_produces_empty_feed",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/minimal_no_items.model",
          "generated": false
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": true
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Atom", "type": "t_feed", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_entry", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_title", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_link", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_generator", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_author", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_name", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_summary", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_content", "expected": 0 },
        { "kind": "count", "model": "Atom", "type": "t_published", "expected": 0 }
      ]
    },
    {
      "name": "single_item_all_mapped_children",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/single_item_all_mapped.model",
          "generated": false
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": true
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Atom", "type": "t_feed", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_entry", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_title", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_link", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_generator", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_author", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_name", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_summary", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_content", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_published", "expected": 1 },
        { "kind": "featureValues", "model": "Atom", "type": "t_title", "feature": "text", "expected": ["Title A"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_link", "feature": "a_href", "expected": ["http://example.org/a"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_generator", "feature": "a_href", "expected": ["genA"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_name", "feature": "text", "expected": ["Alice"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_summary", "feature": "text", "expected": ["Desc A"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_content", "feature": "text", "expected": ["Content A"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_published", "feature": "text", "expected": ["2024-01-01"] },
        { "kind": "pathValues", "model": "Atom", "type": "t_author", "path": "e_name.text", "expected": ["Alice"] }
      ]
    },
    {
      "name": "multiple_items_mixed_and_duplicates",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/multiple_items_mixed.model",
          "generated": false
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": true
        }
      ],
      "assertions": [
        { "kind": "count", "model": "Atom", "type": "t_feed", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_entry", "expected": 2 },
        { "kind": "count", "model": "Atom", "type": "t_title", "expected": 3 },
        { "kind": "count", "model": "Atom", "type": "t_link", "expected": 2 },
        { "kind": "count", "model": "Atom", "type": "t_generator", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_author", "expected": 2 },
        { "kind": "count", "model": "Atom", "type": "t_name", "expected": 2 },
        { "kind": "count", "model": "Atom", "type": "t_summary", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_content", "expected": 1 },
        { "kind": "count", "model": "Atom", "type": "t_published", "expected": 2 },
        { "kind": "featureValues", "model": "Atom", "type": "t_title", "feature": "text", "expected": ["T1", "T1b", "T2"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_link", "feature": "a_href", "expected": ["http://e/1", ""] },
        { "kind": "featureValues", "model": "Atom", "type": "t_generator", "feature": "a_href", "expected": ["gen1"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_name", "feature": "text", "expected": ["Bob", ""] },
        { "kind": "featureValues", "model": "Atom", "type": "t_summary", "feature": "text", "expected": ["D1"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_content", "feature": "text", "expected": ["C1"] },
        { "kind": "featureValues", "model": "Atom", "type": "t_published", "feature": "text", "expected": ["P1", "P2"] },
        { "kind": "pathValues", "model": "Atom", "type": "t_author", "path": "e_name.text", "expected": ["Bob", ""] }
      ]
    }
  ]
}
```

```xml file=models/minimal_no_items.model
<t_rss/>
```

```xml file=models/single_item_all_mapped.model
<t_rss>
  <t_item>
    <t_title>Title A</t_title>
    <t_link>http://example.org/a</t_link>
    <t_generator>genA</t_generator>
    <t_dc:creator>Alice</t_dc:creator>
    <t_description>Desc A</t_description>
    <t_content:encoded>Content A</t_content:encoded>
    <t_pubDate>2024-01-01</t_pubDate>
  </t_item>
</t_rss>
```

```xml file=models/multiple_items_mixed.model
<t_rss>
  <t_item>
    <t_title>T1</t_title>
    <t_title>T1b</t_title>
    <t_link>http://e/1</t_link>
    <t_generator>gen1</t_generator>
    <t_dc:creator>Bob</t_dc:creator>
    <t_description>D1</t_description>
    <t_content:encoded>C1</t_content:encoded>
    <t_pubDate>P1</t_pubDate>
  </t_item>
  <t_item>
    <t_title>T2</t_title>
    <t_link></t_link>
    <t_dc:creator></t_dc:creator>
    <t_pubDate>P2</t_pubDate>
  </t_item>
</t_rss>
```