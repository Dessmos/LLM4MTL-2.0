"""Which implementation runs each contract stage.

Both entry points -- the stage service n8n calls and the local runner -- look a
stage up here, so neither needs the other to find the code behind a stage id.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from llm4mtl.conventions import default_test_project_dir, language_config
from llm4mtl.run_store.models import RunPaths
from llm4mtl.stages.models import PipelineConfig, StageResult
from llm4mtl.stages.test_generation import TestGenerationAdapter
from llm4mtl.stages.transformation_parser import TransformationParserAdapter
from llm4mtl.stages.transformation_validation import TransformationValidationAdapter
from llm4mtl.vocabulary import (
    EXECUTION_STAGE_ID,
    EXTRACT_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_ID,
    SYNTAX_VALIDATION_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_ID,
)
from llm4mtl.workspace import materialize_engine

StageCallable = Callable[[PipelineConfig, bool], StageResult]

# Contract stages that execute Maven, and therefore need a run-local copy of
# the language's engine before they start.
WORKSPACE_STAGES = frozenset(
    {TECHNICAL_VALIDATION_STAGE_ID, REFERENCE_VALIDATION_STAGE_ID, EXECUTION_STAGE_ID}
)


class StageImplementations:
    """The stage implementations one entry point runs, keyed by contract stage id."""

    def __init__(self) -> None:
        self.tests = TestGenerationAdapter()
        self.parser = TransformationParserAdapter()
        self.transformations = TransformationValidationAdapter()

    def implementation(self, stage: str) -> StageCallable:
        """The callable that runs contract stage ``stage``.

        Resolved on every call, so a replaced implementation is the one returned.
        Raises ``KeyError`` for a stage id the contract does not define.
        """
        implementations: dict[str, StageCallable] = {
            EXTRACT_STAGE_ID: self.tests.extract,
            SYNTAX_VALIDATION_STAGE_ID: self.parser.parse,
            TECHNICAL_VALIDATION_STAGE_ID: self.tests.technical_validation,
            REFERENCE_VALIDATION_STAGE_ID: self.tests.reference_validation,
            EXECUTION_STAGE_ID: self.transformations.semantic_validation,
        }
        return implementations[stage]


def prepare_workspace(run_dir: Path, language: str) -> Path:
    """Atomically materialize a run-local copy of the language's engine."""
    config = language_config(language)
    return materialize_engine(
        default_test_project_dir(config),
        RunPaths(run_dir).workspaces_dir,
        config.language_key,
    )
