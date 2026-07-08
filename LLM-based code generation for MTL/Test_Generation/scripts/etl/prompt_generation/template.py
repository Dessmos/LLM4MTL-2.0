"""Task-agnostic body of the test-generation prompt.

Everything here is identical for every task: it must not mention any concrete
metamodel, type, or transformation. All task-specific facts come from the
deterministic contract header and task-context block instead.
"""

from __future__ import annotations


PROMPT_INTRO = (
    "You are generating **semantic test specifications and source input model "
    "files** for one ETL transformation task. Base every expectation strictly on "
    "the ETL rules and metamodels given below."
)


PROMPT_BODY = """\
## Critical constraints
1. **Do NOT generate Java or JUnit code.** The Java test harness is produced
   deterministically by the pipeline from your JSON.
2. **Do NOT depend on or reuse existing manually written semantic tests.** Derive
   cases only from the ETL rules and metamodels above.
3. **Use only the runtime model names, metamodel URIs, and types from the
   deterministic contract.** Do not invent, rename, or substitute metamodels,
   URIs, namespaces, or type names.
4. Generated suites are accepted only after **technical validation** (schema and
   contract consistency) and **reference validation** (behaviour matches the
   reference ETL).
5. Assertions must state **externally observable target-model facts** inferred
   from the ETL semantics:
   - exact target element counts,
   - exact attribute/feature values,
   - exact references/links and their direction,
   - explicit absence of superfluous target elements.

## Output format (strict)
Return **only** fenced file blocks, with no prose outside them:

```json file=semantic_cases.json
...content...
```

```xml file=models/<name>.model
...content...
```

## Required JSON schema (task-generic)
`semantic_cases.json` top-level fields: `schemaVersion`, `testClass`,
`transformation`, `metamodels`, `tests`.

- `metamodels[]`: `name`, `uri` (the metamodelUri from the contract; omit `uri`
  for plainXml models).
- `tests[]`: `name`, `models`, `assertions`.
- `models[]`: `name` (equal to a runtime model name from the contract), `kind`
  (`"emf"` or `"plainXml"`), `role` (`"source"` or `"target"`), `path` (for
  source models you emit), `generated` (boolean), `metamodelUri` (EMF models
  only, exactly as in the contract).
- `assertions[]` may use only these generic kinds: `count`, `featureValues`,
  `objects`, `pathValues`, `referencePairs`.

Canonical assertion payloads:

```json
{"kind": "count", "model": "<target runtime model>", "type": "<type>", "expected": 0}
{"kind": "featureValues", "model": "<target runtime model>", "type": "<type>", "feature": "<feature>", "expected": ["value"]}
{"kind": "pathValues", "model": "<target runtime model>", "type": "<type>", "path": "<feature.or.reference.path>", "expected": ["value"]}
{"kind": "objects", "model": "<target runtime model>", "type": "<type>", "features": ["feature"], "expected": [{"feature": "value"}]}
{"kind": "referencePairs", "model": "<target runtime model>", "type": "<type>", "source": "<source.path>", "target": "<target.path>", "expected": [{"source": "a", "target": "b"}]}
```

Do **not** use alternate primary keys such as `value`, `values`, `equals`,
`ids`, `pairs`, `sourceType`, `targetType`, `where`, or `match`. Use the
canonical `expected` field and the canonical path fields above.

Do **not** introduce transformation-specific schema fields such as
`expectedNodes` / `expectedEdges`.

## Test design requirements
- Cover positive and edge scenarios implied by the ETL: empty/minimal source,
  one instance per mapped source type, mixed instances across mapped types, and
  duplicate/empty values where the metamodel allows.
- For each scenario, assert the exact number of produced target elements and
  their exact feature values.
- Include assertions that rule out unexpected target elements beyond those
  justified by matched source elements.
- Keep every assertion precise and machine-checkable using the generic kinds.
- Emit each source input model as a fenced model file and reference it from
  `models[].path`.

Now produce the files."""
