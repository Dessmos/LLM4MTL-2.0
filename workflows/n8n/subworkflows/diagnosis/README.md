# LLM semantic-failure diagnosis subworkflow

`llm-diagnosis.json` reads the immutable report produced by `diagnosis report`.
It is called only after:

1. the generated transformation passed syntax validation;
2. one semantic assertion failed against the generated transformation.

It sends the report's exact ten-field `source_diagnosis.evidence_bundle` to a
selected LLM, validates the verdict, persists the existing diagnosis artifact
through the stage service, and returns:

- `transformation_defect`
- `test_defect`
- `ambiguous`

The workflow never refines an artifact itself. The parent workflow owns routing
from the classification to transformation refinement, test refinement, or stop.

The prompt is an immutable input stored outside the workflow:

```text
prompt_assets/diagnosis/semantic_failure_diagnosis.md
```

The n8n container reads it from
`/data/diagnosis_prompts/semantic_failure_diagnosis.md`. Both supplied
Docker Compose configurations mount that directory read-only. Edit the prompt
asset rather than the workflow JSON.

## Required input

The parent `Execute Sub-workflow` node passes one item:

```json
{
  "run_id": "run-123",
  "outcome_code": "SEMANTIC_EXECUTION_FAILED",
  "execution_attempt": 1,
  "diagnosis_provider": "openai",
  "failure_report_path": "artifacts/work/runs/run-123/diagnosis-evidence/case-1/assertion-001.json"
}
```

The report path is mandatory and must identify this run under `artifacts/work`.
The workflow does not search for a report, case, assertion, model snapshot,
Surefire report, or structured difference. Supported `diagnosis_provider`
values are `openai`, `anthropic`, and `google`. Choose the concrete
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
  "classification": "transformation_defect",
  "confidence": "high",
  "reasoning_summary": "The expected target node is missing from the actual target model.",
  "evidence": ["missing_elements contains the required target node"],
  "test_case_id": "case-1",
  "assertion_id": "assertion-001"
}
```

Before validation, the workflow stores the exact system/user request and the
raw LLM text. After validation, it stores the complete structured verdict.
These trace artifacts are grouped by semantic-execution attempt and n8n
execution so an n8n retry cannot overwrite the earlier evidence:

```text
artifacts/work/runs/<run-id>/
  responses/source-diagnosis/
    execution-attempt-NNN/
      n8n-execution-<id>__diagnosis_request.json
      n8n-execution-<id>__diagnosis_raw_response.txt
      n8n-execution-<id>__diagnosis_result.json
```

The `execution-attempt-NNN` directory is created by the stage service when it
prepares the evidence, not by the workflow: a write node cannot create the path
it writes to, and the `mkdir` alternative needs the Execute Command node, which
a default n8n container does not ship. The n8n execution id therefore names the
files instead of a further directory level, which is what keeps an n8n retry
from overwriting the earlier trace.

The workflow also maps the verdict to the existing schema-validated canonical
diagnosis artifact. The parent workflow owns all routing from `classification`.
The verdict is a result other work consumes, so the stage service stores it
outside the run rather than among that run's state:

```text
artifacts/work/diagnoses/<run-id>/attempt-NNN/diagnosis.json
```

Only the trace above stays in the run. Nothing in the run points at the verdict;
the run id is the link.
