"""The shared Python stages n8n drives through the stage service.

Each stage selects its inputs from a :class:`~llm4mtl.stages.models.PipelineConfig`,
does deterministic work through ``semantic_tests`` and ``languages``, and returns
a :class:`~llm4mtl.stages.models.StageResult` of facts. How a result is recorded
is ``stage_recording``'s concern and what it means to n8n is ``stage_contract``'s.
"""
