# Fixed held-out suites

Place the frozen campaign data below a version directory and do not generate it
from evaluated runs:

```text
heldout-v1/
  <language>/
    <task>/
      metadata.json
      semantic_cases.json
      models/
```

`metadata.json` contains a stable `id`; every semantic case `name` is a stable
held-out test id. Names must also remain distinct after deterministic Java method
sanitisation. The production workflow never reads this tree.
