# LLM semantic-failure diagnosis subworkflow

`llm-diagnosis.json` is called only after:

1. the generated transformation passed syntax validation;
2. the generated test suite passed technical validation;
3. the test suite passed against the reference transformation;
4. the same suite failed against the generated transformation.

It sends a normalized evidence bundle to a selected LLM, validates a
`schemas/diagnosis.schema.json` object, persists it through the stage service,
and returns the diagnosis fields plus its attempt and artifact path:

- `TRANSFORMATION_DEFECT`
- `TEST_DEFECT`
- `AMBIGUOUS`

The workflow never refines an artifact itself. The parent workflow owns routing
from the classification to transformation refinement, test refinement, or stop.

The prompt is an immutable input stored outside the workflow:

```text
prompt_assets/diagnosis/semantic_failure_diagnosis.prompt.json
```

The n8n container reads it from
`/data/diagnosis_prompts/semantic_failure_diagnosis.prompt.json`. Both supplied
Docker Compose configurations mount that directory read-only. Edit the prompt
asset rather than the workflow JSON.

## Required input

The parent `Execute Sub-workflow` node passes one item:

```json
{
  "run_id": "run-123",
  "language": "etl",
  "task": "Tree2Graph",
  "diagnosis_provider": "openai",
  "evidence_ref": "runs/run-123/stages/execution/attempts/attempt-001/result.json",
  "prechecks": {
    "transformation_syntax_valid": true,
    "test_technical_valid": true,
    "test_reference_valid": true,
    "generated_transformation_tests_pass": false
  },
  "task_contract": {},
  "metamodel_context": {},
  "reference_transformation": {
    "path": "benchmark/tasks/etl/references/Tree2Graph.etl",
    "code": "..."
  },
  "transformation": {
    "path": "runs/run-123/transformations/candidate-001/transformation.etl",
    "model": "claude-sonnet-4",
    "strategy": "grammar",
    "syntax_validation": {},
    "code": "..."
  },
  "test_suite": {
    "path": "runs/run-123/suites/suite-001",
    "model": "gpt-5",
    "strategy": "few_shot",
    "semantic_cases": {},
    "java_sources": {
      "GeneratedTree2GraphSemanticTests.java": "..."
    },
    "models": {
      "models/single_root.model": "..."
    }
  },
  "reference_validation": {
    "status": "REFERENCE_VALIDATED",
    "tests_pass": true,
    "maven_output": "..."
  },
  "execution": {
    "status": "failed",
    "failure_stage": "test_failure",
    "error_summary": "expected: <1> but was: <0>",
    "maven_output": "...",
    "surefire_reports": {}
  }
}
```

`task_contract`, `metamodel_context`, `reference_transformation`,
`reference_validation`, and detailed test-model files are optional but improve
the diagnosis. Transformation source, at least one test representation, and
execution-failure evidence are mandatory.

Supported `diagnosis_provider` values are `openai`, `anthropic`, `google`, and
the `gemini` alias. The parent selects only the company. Choose the concrete
model directly in `OpenAI Diagnosis Model`, `Anthropic Diagnosis Model`, or
`Google Diagnosis Model` using the standard n8n model list, exactly as in the
generation workflows. The imported workflow references the same n8n
credentials as those workflows; reconnect a credential if the local n8n
instance uses different credential IDs.

Immutable inputs are not copied into `artifacts/`: task contracts, reference
transformations, and metamodels remain under `benchmark/`, while prompt
templates, grammars, and few-shot examples remain under `prompt_assets/`.

## Output

The last node returns exactly:

```json
{
  "schema_version": "1.0",
  "classification": "TRANSFORMATION_DEFECT",
  "evidence_ref": "runs/run-123/stages/execution/attempts/attempt-001/result.json",
  "rationale": "The validated assertion expected one target node but the generated transformation produced none.",
  "provider": "openai",
  "model": "gpt-5",
  "created_at": "2026-07-23T12:00:00.000Z",
  "attempt": 1,
  "artifact": "responses/failure-diagnosis/attempt-001/diagnosis.json"
}
```

The final HTTP node persists the normalized object through the Python stage
service and returns it with `attempt` and `artifact`. The parent workflow should
Switch on `classification`. Each attempt is stored as:

```text
artifacts/work/runs/<run-id>/
  responses/failure-diagnosis/attempt-NNN/diagnosis.json
```
