"""Single source of truth for repository paths.

Every module that needs a repository location asks this one, so a layout change
is one edit here rather than a search through the package. ``REPO_ROOT`` is
derived from this file's own location, :class:`TargetLayout` names the top-level
areas of the repository, and :class:`ArtifactRoots` describes the writable
artifact tree below ``artifacts/work`` together with the spelling under which
the n8n container reaches it.

Nothing else may derive one of these locations from another: a module that knows
a run directory asks :class:`ArtifactRoots` where the run's diagnoses are rather
than joining path segments of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


# ``paths.py`` lives at <repo_root>/pipeline/src/llm4mtl/paths.py
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# Where docker-compose mounts ``artifacts/work`` for the n8n container. n8n reads
# and writes run artifacts through this prefix, so every path Python hands to a
# workflow is spelled from here, and only here.
N8N_ARTIFACTS_MOUNT = PurePosixPath("/data/artifacts")


@dataclass(frozen=True)
class ArtifactRoots:
    """The writable artifact tree one process serves.

    One launch of the pipeline is a *batch*; every run it creates lives below
    that batch, and the diagnoses of those runs mirror the same nesting in their
    own area:

    .. code-block:: text

        <artifacts_work>/runs/<batch-id>/<run-id>/
        <artifacts_work>/diagnoses/<batch-id>/<run-id>/attempt-NNN/

    Nothing else may derive one of these locations from another: a module that
    knows a run directory asks this class where the run's diagnoses are, rather
    than reading the directory name back and joining it somewhere else. The stage
    service and the local runner hold one instance each, which is also what the
    tests redirect into a temporary tree.
    """

    artifacts_work: Path

    @property
    def runs(self) -> Path:
        return self.artifacts_work / "runs"

    @property
    def diagnoses(self) -> Path:
        """Failure diagnoses, kept out of the runs that produced them.

        A run directory is working state — workspaces, locks, the build log, the
        evidence a stage happened to record. A diagnosis is a result other work
        consumes: refinement routes on it, reporting counts it, analysis reads it
        across runs. Handing that to a consumer meant handing them the whole run
        and telling them which parts to ignore, so it lives in its own area,
        keyed by the batch and run that produced it.
        """
        return self.artifacts_work / "diagnoses"

    def batch_dir(self, batch_id: str) -> Path:
        return self.runs / batch_id

    def run_dir(self, batch_id: str, run_id: str) -> Path:
        return self.batch_dir(batch_id) / run_id

    def batch_diagnoses_dir(self, batch_id: str) -> Path:
        return self.diagnoses / batch_id

    def run_diagnoses_dir(self, batch_id: str, run_id: str) -> Path:
        return self.batch_diagnoses_dir(batch_id) / run_id

    def n8n_path(self, path: Path) -> str:
        """``path`` as the n8n container sees it through the artifacts mount.

        Raises :class:`ValueError` for a path outside this artifact tree: n8n
        cannot reach it, so handing over a spelling would only defer the error
        to a workflow node that has less to say about it.
        """
        relative = Path(path).resolve().relative_to(self.artifacts_work.resolve())
        return (N8N_ARTIFACTS_MOUNT / relative.as_posix()).as_posix()


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
    def artifact_roots(self) -> ArtifactRoots:
        """The batch/run/diagnosis layout below ``artifacts/work``."""
        return ArtifactRoots(self.artifacts_work)

    @property
    def runs(self) -> Path:
        return self.artifact_roots.runs

    @property
    def diagnoses(self) -> Path:
        return self.artifact_roots.diagnoses

    def batch_dir(self, batch_id: str) -> Path:
        return self.artifact_roots.batch_dir(batch_id)

    def run_dir(self, batch_id: str, run_id: str) -> Path:
        return self.artifact_roots.run_dir(batch_id, run_id)

    def batch_diagnoses_dir(self, batch_id: str) -> Path:
        return self.artifact_roots.batch_diagnoses_dir(batch_id)

    def run_diagnoses_dir(self, batch_id: str, run_id: str) -> Path:
        return self.artifact_roots.run_diagnoses_dir(batch_id, run_id)

    # Engines, uniform per language
    def engine_parser(self, language: str) -> Path:
        return self.engines / language / "parser"

    def engine_harness(self, language: str) -> Path:
        return self.engines / language / "harness"

    # Inputs, uniform per language / task
    def benchmark_task(self, language: str, task: str) -> Path:
        return self.benchmark / "tasks" / language / task


TARGET = TargetLayout()


def repository_relative(path: Path) -> str:
    """``path`` as a repository-relative POSIX string, or its absolute form.

    How a path is written into an artifact, so that a run recorded on one
    machine reads the same on another. Everything the pipeline records lives
    inside the repository; a path that does not is kept absolute rather than
    reached for with ``..``, because a stored ``..`` would resolve against
    whatever directory happened to read it.

    Use :func:`require_repository_relative` where an escaping path is a fault
    rather than an unusual location.
    """
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def require_repository_relative(path: Path) -> str:
    """``path`` as a repository-relative POSIX string, refusing to leave it.

    The same spelling as :func:`repository_relative`, for the callers where a
    path outside the repository is a fault: an input resolved from somewhere it
    could not have come from, or evidence that would be unreadable to anyone
    else. Raises :class:`ValueError`; a caller with its own error vocabulary
    translates it at its own boundary.
    """
    return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
