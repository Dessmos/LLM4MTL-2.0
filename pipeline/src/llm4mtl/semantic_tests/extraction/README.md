Stage 1 of the determenistic pipeline lives here


LLM generate a file like this:
-------------------------------
Test for Tree2Graph:

```json file=semantic_cases.json
{ "tests": [ { "name": "nodes are preserved", "assertions": [...] } ] }
```

```xml file=models/input.model
<tree>...</tree>
```
-------------------------------

And the goal is to get:
semantic_cases.json                     checked spec
GeneratedTree2GraphSemanticTest.java    harness
models/input.model
metadata.json                           where did it come from

cli.py                      - Every execution in every run, passes through - extract_one
discovery.py                - decides which ansears to work witf
models.py                   - data stracture fur the suite
writer.py                   - saves files locally
parser.py                   - cut .md file into different files / 
                              Finds triple-quoted blocks and extracts the filename 
                              from each one—specifically from the block's own line.