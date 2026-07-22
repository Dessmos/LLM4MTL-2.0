"""Layout of an experiment directory under ``artifacts/work/experiments/<id>/``.

An experiment groups the runs of a matrix/ablation and owns the experiment-level
results (aggregation + significance over many runs):

* ``experiment-manifest.json`` — immutable experiment config + provenance.
* ``run-index.json`` — the mutable list of run ids that belong to the experiment.
* ``aggregate-metrics/`` / ``ablation/`` / ``significance/`` — computed outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ExperimentPaths:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "experiment-manifest.json"

    @property
    def run_index(self) -> Path:
        return self.root / "run-index.json"

    @property
    def aggregate_metrics_dir(self) -> Path:
        return self.root / "aggregate-metrics"

    @property
    def ablation_dir(self) -> Path:
        return self.root / "ablation"

    @property
    def significance_dir(self) -> Path:
        return self.root / "significance"
