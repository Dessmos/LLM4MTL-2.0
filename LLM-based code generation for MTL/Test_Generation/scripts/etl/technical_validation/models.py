"""Data structures and constants for generated-suite technical validation."""

from __future__ import annotations

from common.paths import ETL_CONFIG
from etl.suites.models import CandidateSuite


LANGUAGE = ETL_CONFIG.language
RESULT_COLUMNS = [
    "language",
    "task",
    "suite_id",
    "llm",
    "strategy",
    "java_present",
    "models_present",
    "contract_valid",
    "compiles",
    "models_load",
    "junit_executes",
    "technically_valid",
    "maven_exit_code",
    "error_summary",
]
