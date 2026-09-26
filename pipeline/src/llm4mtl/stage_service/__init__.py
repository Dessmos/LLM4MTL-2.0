"""HTTP stage service: a thin FastAPI wrapper that lets n8n drive the pipeline.

Transport only, no business logic: ``POST /batches`` claims a batch,
``POST /batches/{batch_id}/runs`` creates a run in it, and
``POST /batches/{batch_id}/runs/{run_id}/stages/{stage}`` runs one stage and
returns the standard stage-result payload (status + outcome_code + artifacts).
Other endpoints resolve prompt inputs, prepare refinements, record generations,
diagnoses and results, and read batch, run and stage state. See
``docs/runner-api.md``.
"""
