# Data flow

> Status: **skeleton (Stage 0)**.

End-to-end vertical slice (to be documented fully in Stage 5):

```text
prompt-building
  → transformation generation (n8n)      → transformations/candidate-NNN/
  → syntax-validation (Workflow A)
  → semantic-test generation (n8n)       → responses/semantic-test-generation/
  → extraction                           → suites/suite_NNN/semantic_cases.json + models/
  → codegen (deterministic Java/JUnit)   → suites/suite_NNN/Generated...Tests.java
  → technical-validation
  → reference-validation                 → validated suites
  → execution (validated suites × parsable transformations)
  → diagnosis (only on ambiguous failure; LLM call in n8n)
  → refinement (iteration-NNN)
  → evaluation (run metrics) → aggregation + significance (experiment level)
```
