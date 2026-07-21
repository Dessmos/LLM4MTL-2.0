"""Semantic test generation pipeline (Workflow B).

Sub-stages: extraction (raw response -> semantic_cases.json + models), codegen
(deterministic JUnit harness), technical_validation, reference_validation, plus
shared suite helpers and the semantic-case spec.
"""
