"""Data structures for generated-transformation validation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from etl.suites.models import CandidateSuite


RESULT_COLUMNS = [
    "run_id",
    "language",
    "task",
    "transformation_model",
    "transformation_strategy",
    "transformation_path",
    "transformation_sha256",
    "test_model",
    "test_strategy",
    "suite_id",
    "suite_path",
    "suite_sha256",
    "status",
    "failure_stage",
    "compiles",
    "executes",
    "tests_pass",
    "maven_exit_code",
    "timed_out",
    "error_summary",
    "artifact_dir",
]


@dataclass(frozen=True)
class ValidatedSuite:
    path: Path
    task: str
    llm: str
    strategy: str
    suite_id: str

    def as_candidate(self) -> CandidateSuite:
        return CandidateSuite(
            path=self.path,
            task=self.task,
            llm=self.llm,
            strategy=self.strategy,
            suite_id=self.suite_id,
        )


@dataclass(frozen=True)
class GeneratedTransformation:
    path: Path
    task: str
    llm: str
    strategy: str


@dataclass(frozen=True)
class ValidationPair:
    suite: ValidatedSuite
    transformation: GeneratedTransformation


@dataclass(frozen=True)
class TransformationValidationResult:
    pair: ValidationPair
    run_id: str
    transformation_sha256: str
    suite_sha256: str
    status: str
    failure_stage: str
    compiles: bool
    executes: bool
    tests_pass: bool
    maven_exit_code: int | str
    timed_out: bool
    error_summary: str
    maven_output: str
    artifact_dir: str = ""

    def with_artifact_dir(self, artifact_dir: str) -> "TransformationValidationResult":
        return replace(self, artifact_dir=artifact_dir)

    def as_row(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "language": "ETL",
            "task": self.pair.suite.task,
            "transformation_model": self.pair.transformation.llm,
            "transformation_strategy": self.pair.transformation.strategy,
            "transformation_path": str(self.pair.transformation.path),
            "transformation_sha256": self.transformation_sha256,
            "test_model": self.pair.suite.llm,
            "test_strategy": self.pair.suite.strategy,
            "suite_id": self.pair.suite.suite_id,
            "suite_path": str(self.pair.suite.path),
            "suite_sha256": self.suite_sha256,
            "status": self.status,
            "failure_stage": self.failure_stage,
            "compiles": str(self.compiles),
            "executes": str(self.executes),
            "tests_pass": str(self.tests_pass),
            "maven_exit_code": str(self.maven_exit_code),
            "timed_out": str(self.timed_out),
            "error_summary": self.error_summary,
            "artifact_dir": self.artifact_dir,
        }
