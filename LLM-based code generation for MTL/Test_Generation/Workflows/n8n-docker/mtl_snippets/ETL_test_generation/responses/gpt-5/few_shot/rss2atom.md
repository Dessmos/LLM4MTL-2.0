```json file=semantic_cases.json
{
  "schemaVersion": "1.0",
  "testClass": "GeneratedRss2AtomSemanticTests",
  "transformation": "rss2atom.etl",
  "metamodels": [
    {"name": "RSS"},
    {"name": "Atom"}
  ],
  "tests": [
    {
      "name": "minimal_rss_no_items_creates_only_feed",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/minimal_no_items.model",
          "generated": true
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": false
        }
      ],
      "assertions": [
        {"kind": "count", "model": "Atom", "type": "t_feed", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_entry", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_title", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_link", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_generator", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_author", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_name", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_summary", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_content", "expected": 0},
        {"kind": "count", "model": "Atom", "type": "t_published", "expected": 0}
      ]
    },
    {
      "name": "single_item_all_mapped_children_create_full_entry",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/single_item_all_mapped.model",
          "generated": true
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": false
        }
      ],
      "assertions": [
        {"kind": "count", "model": "Atom", "type": "t_feed", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_entry", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_title", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_link", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_generator", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_author", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_name", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_summary", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_content", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_published", "expected": 1},
        {"kind": "pathValues", "model": "Atom", "type": "t_title", "path": "text", "expected": ["Item One Title"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_link", "path": "a_href", "expected": ["https://example.org/item1"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_generator", "path": "a_href", "expected": ["https://example.org/gen"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_name", "path": "text", "expected": ["Alice"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_summary", "path": "text", "expected": ["Summary 1"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_content", "path": "text", "expected": ["Content 1"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_published", "path": "text", "expected": ["Mon, 01 Jan 2024 10:00:00 GMT"]}
      ]
    },
    {
      "name": "mixed_multiple_items_with_duplicates_and_empty_values",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/mixed_multiple_items.model",
          "generated": true
        },
        {
          "name": "Atom",
          "kind": "plainXml",
          "role": "target",
          "generated": false
        }
      ],
      "assertions": [
        {"kind": "count", "model": "Atom", "type": "t_feed", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_entry", "expected": 3},
        {"kind": "count", "model": "Atom", "type": "t_title", "expected": 3},
        {"kind": "count", "model": "Atom", "type": "t_link", "expected": 3},
        {"kind": "count", "model": "Atom", "type": "t_generator", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_author", "expected": 2},
        {"kind": "count", "model": "Atom", "type": "t_name", "expected": 2},
        {"kind": "count", "model": "Atom", "type": "t_summary", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_content", "expected": 2},
        {"kind": "count", "model": "Atom", "type": "t_published", "expected": 2},
        {"kind": "pathValues", "model": "Atom", "type": "t_title", "path": "text", "expected": ["Repeat Title", "Repeat Title", ""]},
        {"kind": "pathValues", "model": "Atom", "type": "t_link", "path": "a_href", "expected": ["https://example.org/a", "https://example.org/b", ""]},
        {"kind": "pathValues", "model": "Atom", "type": "t_generator", "path": "a_href", "expected": ["genX"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_name", "path": "text", "expected": ["", "Bob"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_summary", "path": "text", "expected": ["Only summary"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_content", "path": "text", "expected": ["Body A", ""]},
        {"kind": "pathValues", "model": "Atom", "type": "t_published", "path": "text", "expected": ["Date A", "Date C"]}
      ]
    }
  ]
}
```

```xml file=models/minimal_no_items.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss>
  <channel/>
</t_rss>
```

```xml file=models/single_item_all_mapped.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss xmlns:t_dc="urn:dc" xmlns:t_content="urn:content">
  <channel>
    <t_item>
      <t_title>Item One Title</t_title>
      <t_link>https://example.org/item1</t_link>
      <t_generator>https://example.org/gen</t_generator>
      <t_dc:creator>Alice</t_dc:creator>
      <t_description>Summary 1</t_description>
      <t_content:encoded>Content 1</t_content:encoded>
      <t_pubDate>Mon, 01 Jan 2024 10:00:00 GMT</t_pubDate>
    </t_item>
  </channel>
</t_rss>
```

```xml file=models/mixed_multiple_items.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss xmlns:t_dc="urn:dc" xmlns:t_content="urn:content">
  <channel>
    <t_item>
      <t_title>Repeat Title</t_title>
      <t_link>https://example.org/a</t_link>
      <t_generator>genX</t_generator>
      <t_dc:creator></t_dc:creator>
      <t_description>Only summary</t_description>
      <t_content:encoded>Body A</t_content:encoded>
      <t_pubDate>Date A</t_pubDate>
    </t_item>
    <t_item>
      <t_title>Repeat Title</t_title>
      <t_link>https://example.org/b</t_link>
      <t_dc:creator>Bob</t_dc:creator>
      <t_content:encoded></t_content:encoded>
    </t_item>
    <t_item>
      <t_title></t_title>
      <t_link></t_link>
      <t_pubDate>Date C</t_pubDate>
    </t_item>
  </channel>
</t_rss>
```