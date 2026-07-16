"""Data structures and constants for reference validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common.paths import ETL_CONFIG
from etl.suites.models import CandidateSuite


LANGUAGE = ETL_CONFIG.language
RESULT_COLUMNS = [
    "language",
    "task",
    "suite_id",
    "llm",
    "strategy",
    "compiles",
    "executes",
    "reference_pass",
    "valid",
    "maven_exit_code",
    "status",
    "error_summary",
]


@dataclass(frozen=True)
class ReferenceValidationContext:
    etl_test_dir: Path
    references_root: Path
    results_root: Path
    timeout: int
    promote: bool


@dataclass(frozen=True)
class ReferenceValidationResult:
    suite: CandidateSuite
    compiles: bool
    executes: bool
    reference_pass: bool
    valid: bool
    maven_exit_code: int | str
    status: str
    error_summary: str

    def as_row(self) -> dict[str, str]:
        return {
            "language": LANGUAGE,
            "task": self.suite.task,
            "suite_id": self.suite.suite_id,
            "llm": self.suite.llm,
            "strategy": self.suite.strategy,
            "compiles": str(self.compiles),
            "executes": str(self.executes),
            "reference_pass": str(self.reference_pass),
            "valid": str(self.valid),
            "maven_exit_code": str(self.maven_exit_code),
            "status": self.status,
            "error_summary": self.error_summary,
        }
