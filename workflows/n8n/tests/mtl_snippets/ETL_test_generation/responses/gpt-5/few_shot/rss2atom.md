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
      "name": "empty_channel_items_creates_feed_with_no_children",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/rss_empty.model",
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
      "name": "single_item_all_mapped_children_creates_one_entry_with_all_mapped_targets",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/rss_single_full.model",
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
        {"kind": "pathValues", "model": "Atom", "type": "t_title", "path": "text", "expected": ["Item One"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_link", "path": "a_href", "expected": ["https://example.org/one"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_generator", "path": "a_href", "expected": ["https://generator.example.org"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_name", "path": "text", "expected": ["Alice"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_summary", "path": "text", "expected": ["Summary One"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_content", "path": "text", "expected": ["Content One"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_published", "path": "text", "expected": ["Mon, 01 Jan 2024 10:00:00 GMT"]}
      ]
    },
    {
      "name": "mixed_children_and_duplicates_across_items_only_mapped_children_transformed",
      "models": [
        {
          "name": "RSS",
          "kind": "plainXml",
          "role": "source",
          "path": "models/rss_mixed_duplicates.model",
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
        {"kind": "count", "model": "Atom", "type": "t_entry", "expected": 2},
        {"kind": "count", "model": "Atom", "type": "t_title", "expected": 3},
        {"kind": "count", "model": "Atom", "type": "t_link", "expected": 2},
        {"kind": "count", "model": "Atom", "type": "t_generator", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_author", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_name", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_summary", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_content", "expected": 1},
        {"kind": "count", "model": "Atom", "type": "t_published", "expected": 1},
        {"kind": "pathValues", "model": "Atom", "type": "t_title", "path": "text", "expected": ["Repeat", "Repeat", ""]},
        {"kind": "pathValues", "model": "Atom", "type": "t_link", "path": "a_href", "expected": ["https://example.org/a", ""]},
        {"kind": "pathValues", "model": "Atom", "type": "t_generator", "path": "a_href", "expected": ["genA"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_name", "path": "text", "expected": ["Bob"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_summary", "path": "text", "expected": ["Desc A"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_content", "path": "text", "expected": ["Body A"]},
        {"kind": "pathValues", "model": "Atom", "type": "t_published", "path": "text", "expected": ["Tue, 02 Jan 2024 11:00:00 GMT"]}
      ]
    }
  ]
}
```

```xml file=models/rss_empty.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss/>
```

```xml file=models/rss_single_full.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss xmlns:t_dc="urn:dc" xmlns:t_content="urn:content">
  <channel>
    <t_item>
      <t_title>Item One</t_title>
      <t_link>https://example.org/one</t_link>
      <t_generator>https://generator.example.org</t_generator>
      <t_dc:creator>Alice</t_dc:creator>
      <t_description>Summary One</t_description>
      <t_content:encoded>Content One</t_content:encoded>
      <t_pubDate>Mon, 01 Jan 2024 10:00:00 GMT</t_pubDate>
    </t_item>
  </channel>
</t_rss>
```

```xml file=models/rss_mixed_duplicates.model
<?xml version="1.0" encoding="UTF-8"?>
<t_rss xmlns:t_dc="urn:dc" xmlns:t_content="urn:content">
  <channel>
    <t_item>
      <t_title>Repeat</t_title>
      <t_title>Repeat</t_title>
      <t_link>https://example.org/a</t_link>
      <t_generator>genA</t_generator>
      <t_dc:creator>Bob</t_dc:creator>
      <t_description>Desc A</t_description>
      <t_content:encoded>Body A</t_content:encoded>
      <t_pubDate>Tue, 02 Jan 2024 11:00:00 GMT</t_pubDate>
      <unknown>ignored</unknown>
    </t_item>
    <t_item>
      <t_title></t_title>
      <t_link></t_link>
      <otherChild>ignored too</otherChild>
    </t_item>
  </channel>
</t_rss>
```