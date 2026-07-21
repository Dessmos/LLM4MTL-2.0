# n8n ↔ Python contract

> Status: **skeleton (Stage 0)**. Finalised in Stage 5.

n8n invokes each Python stage through the runner and reads back a standard
result (see `schemas/stage-result.schema.json`). **Python reports facts; routing
lives only in n8n.**

## Stage → outcome_code → n8n transition (draft)

| stage | outcome_code (domain) | n8n next step (policy in n8n) |
| --- | --- | --- |
| extract | `EXTRACTED` / `TEST_SPEC_INVALID` | valid → technical; invalid → regenerate test |
| syntax-validation | `SYNTAX_VALID` / `SYNTAX_INVALID` | invalid → repair transformation |
| technical-validation | `TECH_VALID` / `TECH_COMPILE_FAILED` / `TECH_EXEC_FAILED` | valid → reference; else repair test |
| reference-validation | `REFERENCE_VALIDATED` / `REFERENCE_VALIDATION_FAILED` | validated → execute; failed → test defect |
| execution | `SEMANTIC_PASSED` / `SEMANTIC_EXECUTION_FAILED` | passed → evaluate; failed → diagnose |
| diagnosis | `DIAGNOSIS_EVIDENCE_READY` | → n8n LLM-diagnosis subworkflow |
| (diagnosis result) | `TRANSFORMATION_DEFECT` / `TEST_DEFECT` / `AMBIGUOUS` | refine transformation / refine test / stop |
| evaluate | `EVALUATION_COMPLETE` | → reporting |

`infrastructure_error` is orthogonal on every stage and is treated by n8n as
retry/stop, not as an LLM failure. Iteration limits and stop conditions are n8n
policy.
