"""HTTP stage service: a thin FastAPI wrapper that lets n8n drive the pipeline.

Transport only, no business logic: ``POST /runs`` creates a run,
``POST /runs/{run_id}/stages/{stage}`` runs one stage and returns the standard
stage-result payload (status + outcome_code + artifacts), and the ``GET``
endpoints read run/stage state. See ``docs/runner-api.md``.
"""
