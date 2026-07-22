"""Expand an experiment matrix (RQ4 ablation) into concrete run specs.

A matrix is the cartesian product of its axes (tasks x transformation models x
strategies x test models/strategies x variants x seeds); each combination is one
run. Significance is computed at the experiment level over the resulting run set.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

from llm4mtl.experiment_runner.config import load_mapping


@dataclass(frozen=True)
class RunSpec:
    experiment_id: str
    language: str
    task: str
    transformation_model: str
    transformation_strategy: str
    test_model: str
    test_strategy: str
    variant: str
    seed: int

    @property
    def run_id(self) -> str:
        return "__".join(
            [
                self.experiment_id,
                self.language,
                self.task,
                f"t-{self.transformation_model}-{self.transformation_strategy}",
                f"g-{self.test_model}-{self.test_strategy}",
                self.variant,
                f"seed{self.seed}",
            ]
        )


def load_matrix(path: Path) -> dict[str, Any]:
    return load_mapping(Path(path))


def expand_matrix(matrix: dict[str, Any]) -> list[RunSpec]:
    """Return one :class:`RunSpec` per cell of the matrix's cartesian product."""
    experiment_id = str(matrix.get("experiment_id", "experiment"))
    language = str(matrix.get("language", "etl"))
    axes = product(
        matrix.get("tasks", []),
        matrix.get("transformation_models", []),
        matrix.get("transformation_strategies", []),
        matrix.get("test_models", []),
        matrix.get("test_strategies", []),
        matrix.get("variants", ["full"]),
        matrix.get("seeds", [1]),
    )
    return [
        RunSpec(
            experiment_id=experiment_id,
            language=language,
            task=str(task),
            transformation_model=str(transformation_model),
            transformation_strategy=str(transformation_strategy),
            test_model=str(test_model),
            test_strategy=str(test_strategy),
            variant=str(variant),
            seed=int(seed),
        )
        for task, transformation_model, transformation_strategy, test_model, test_strategy, variant, seed in axes
    ]
