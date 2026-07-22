"""Single source of truth for repository paths.

Rationale
---------
Today paths are hard-coded in many places: ``Test_Generation/scripts/common/
paths.py`` (``parents[3]`` plus string literals ``"ETL_Test"`` /
``"Test_Generation"``), the ``Experiment_Runner`` adapters, Maven ``cwd`` values,
and ``docker-compose`` volume mounts. Every migration step therefore becomes a
wide, error-prone edit.

This module centralises repository paths. It declares two coordinated views:

* LEGACY — historical pre-v5 locations, retained only for migration audits.
* TARGET — the active v5 layout at the git repository root.

Active code must use REPO_ROOT or TARGET. Run this module to print the historical
migration map.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ``paths.py`` lives at <repo_root>/pipeline/src/llm4mtl/paths.py
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# The current, pre-migration project folder that still holds every module.
LEGACY_PROJECT_ROOT: Path = REPO_ROOT / "LLM-based code generation for MTL"


@dataclass(frozen=True)
class LegacyLayout:
    """Component locations BEFORE migration (inside the nested project folder)."""

    root: Path = LEGACY_PROJECT_ROOT

    # --- Java/Maven engines (moved verbatim in Stage 2; logic never edited) ---
    @property
    def etl_parser(self) -> Path:
        return self.root / "ETL_Parser"

    @property
    def etl_harness(self) -> Path:
        return self.root / "ETL_Test"

    @property
    def atl_parser(self) -> Path:
        return self.root / "ATL_Parser"

    @property
    def atl_harness(self) -> Path:
        return self.root / "ATL_Tests"

    @property
    def qvto_parser(self) -> Path:
        return self.root / "QVT-O_parser"

    @property
    def qvto_harness(self) -> Path:
        return self.root / "QVT-O_Test"

    @property
    def reactions_parser(self) -> Path:
        return self.root / "Reactions_Langauge_Parser"

    @property
    def reactions_parser_antlr(self) -> Path:
        return self.root / "ReactionParser"

    @property
    def reactions_harness(self) -> Path:
        return self.root / "Reactions_Language_Tests"

    @property
    def reactions_harness_eval(self) -> Path:
        return self.root / "Reactions_Language_Evaluate_Tests"

    # --- Our Python (reorganised in Stage 1) ---
    @property
    def test_generation(self) -> Path:
        return self.root / "Test_Generation"

    @property
    def transformation_validation(self) -> Path:
        return self.root / "Transformation_Validation"

    @property
    def experiment_runner(self) -> Path:
        return self.root / "Experiment_Runner"

    @property
    def significant_test(self) -> Path:
        return self.root / "Significant_Test"

    @property
    def experiments(self) -> Path:
        return self.root / "experiments"

    # --- n8n (unified in Stage 3) ---
    @property
    def n8n_transformations(self) -> Path:
        return self.root / "Workflows" / "n8n-docker"

    @property
    def n8n_tests(self) -> Path:
        return self.root / "Test_Generation" / "Workflows" / "n8n-docker"

    # --- Specific scripts referenced by the current adapters ---
    @property
    def etl_syntax_driver(self) -> Path:
        return self.etl_parser / "validate_etl_syntax.py"


@dataclass(frozen=True)
class TargetLayout:
    """Component locations in the v5 layout (at the git repository root)."""

    root: Path = REPO_ROOT

    # Top-level areas
    @property
    def schemas(self) -> Path:
        return self.root / "schemas"

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    @property
    def engines(self) -> Path:
        return self.root / "engines"

    @property
    def pipeline(self) -> Path:
        return self.root / "pipeline"

    @property
    def package(self) -> Path:
        return self.pipeline / "src" / "llm4mtl"

    @property
    def benchmark(self) -> Path:
        return self.root / "benchmark"

    @property
    def prompt_assets(self) -> Path:
        return self.root / "prompt_assets"

    @property
    def workflows(self) -> Path:
        return self.root / "workflows" / "n8n"

    @property
    def experiments(self) -> Path:
        return self.root / "experiments"

    @property
    def experiments_presets(self) -> Path:
        return self.experiments / "presets"

    @property
    def experiments_variants(self) -> Path:
        return self.experiments / "variants"

    @property
    def experiments_matrices(self) -> Path:
        return self.experiments / "matrices"

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def artifacts_work(self) -> Path:
        return self.artifacts / "work"

    @property
    def runs(self) -> Path:
        return self.artifacts_work / "runs"

    @property
    def artifact_experiments(self) -> Path:
        return self.artifacts_work / "experiments"

    def experiment_dir(self, experiment_id: str) -> Path:
        return self.artifact_experiments / experiment_id

    # Engines, uniform per language
    def engine_parser(self, language: str) -> Path:
        return self.engines / language / "parser"

    def engine_harness(self, language: str) -> Path:
        return self.engines / language / "harness"

    # Inputs, uniform per language / task
    def benchmark_task(self, language: str, task: str) -> Path:
        return self.benchmark / "tasks" / language / task

    def run_dir(self, run_id: str) -> Path:
        return self.runs / run_id


LEGACY = LegacyLayout()
TARGET = TargetLayout()

# Migration map (legacy -> target) used by Stages 1-2 and by the self-check.
# Kept as data so a stage can move a component and update one entry here.
MIGRATION_MAP: dict[str, tuple[Path, Path]] = {
    "etl/parser": (LEGACY.etl_parser, TARGET.engine_parser("etl")),
    "etl/harness": (LEGACY.etl_harness, TARGET.engine_harness("etl")),
    "atl/parser": (LEGACY.atl_parser, TARGET.engine_parser("atl")),
    "atl/harness": (LEGACY.atl_harness, TARGET.engine_harness("atl")),
    "qvto/parser": (LEGACY.qvto_parser, TARGET.engine_parser("qvto")),
    "qvto/harness": (LEGACY.qvto_harness, TARGET.engine_harness("qvto")),
    "reactions/parser": (LEGACY.reactions_parser, TARGET.engine_parser("reactions")),
    "reactions/parser-antlr": (LEGACY.reactions_parser_antlr, TARGET.engines / "reactions" / "parser-antlr"),
    "reactions/harness": (LEGACY.reactions_harness, TARGET.engine_harness("reactions")),
    "pipeline/test_generation": (LEGACY.test_generation, TARGET.package),
    "pipeline/transformation_validation": (LEGACY.transformation_validation, TARGET.package / "transformation_execution"),
    "pipeline/experiment_runner": (LEGACY.experiment_runner, TARGET.package),
    "pipeline/significant_test": (LEGACY.significant_test, TARGET.package / "evaluation"),
    "n8n/transformations": (LEGACY.n8n_transformations, TARGET.workflows / "transformations"),
    "n8n/tests": (LEGACY.n8n_tests, TARGET.workflows / "tests"),
}


def _report() -> str:
    lines = [
        "LLM4MTL path configuration (v5)",
        f"REPO_ROOT           : {REPO_ROOT}",
        f"LEGACY_PROJECT_ROOT : {LEGACY_PROJECT_ROOT}  (exists={LEGACY_PROJECT_ROOT.is_dir()})",
        "",
        "Migration map (legacy -> target):",
    ]
    for key, (legacy, target) in MIGRATION_MAP.items():
        mark = "ok" if legacy.exists() else "MISSING"
        lines.append(f"  [{mark:>7}] {key}")
        lines.append(f"            from: {legacy}")
        lines.append(f"            to  : {target}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_report())
