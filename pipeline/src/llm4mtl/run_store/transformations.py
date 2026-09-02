"""The run's own copy of every transformation it judged.

Generation writes its raw response into the current run. The first stage that
judges that response adopts it as an immutable transformation input, and every
later stage of the same artifact iteration reads the adopted copy.

So the first stage of a run that judges a transformation *adopts* it — copies it
once into the run — and every later stage of that run judges the copy. The
shared tree stays exactly what it was, a convenience cache of the latest
generation; the run directory becomes the source of truth that evidence,
manifests and evaluation cite.

Refinement regenerates the transformation, so the copy is per refinement
iteration::

    runs/<run-id>/transformation/iteration-000/<Task>.<ext>
    runs/<run-id>/transformation/iteration-000/metadata.json

The file keeps its task name because the execution stage pairs a suite with a
transformation by that stem; renaming it to ``generated.etl`` would silently
produce zero execution pairs.

Adoption is idempotent and write-once. Re-running a stage of the same iteration
re-adopts the identical bytes and reuses the copy. Different bytes under the same
iteration mean generation overwrote the input mid-run, which is precisely the
loss this module exists to prevent, so it is refused instead of recorded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.paths import REPO_ROOT
from llm4mtl.run_store.models import RunPaths
from llm4mtl.serialization.json_io import read_json, write_json
from llm4mtl.transformation_execution.hashing import file_sha256

SCHEMA_VERSION = "1.0"
METADATA_FILENAME = "metadata.json"
# ``<run-id>_<NNN>``: the master workflow derives the suite id from the run id
# and the refinement iteration, so the iteration is readable from it without a
# second field that could disagree with it.
SUITE_ITERATION = re.compile(r"_(\d{3})$")


class TransformationAdoptionError(ValueError):
    """Raised when a run cannot take an immutable copy of its transformation."""


@dataclass(frozen=True)
class AdoptedTransformations:
    """One refinement iteration's immutable transformation inputs."""

    iteration: int
    directory: Path
    paths: tuple[Path, ...]

    @property
    def metadata(self) -> Path:
        return self.directory / METADATA_FILENAME


def iteration_from_suite_id(suite_id: str | None) -> int:
    """The refinement iteration a suite id encodes; 0 when it encodes none."""
    if not suite_id:
        return 0
    match = SUITE_ITERATION.search(suite_id)
    return int(match.group(1)) if match else 0


def transformation_dir(paths: RunPaths, iteration: int) -> Path:
    if iteration < 0:
        raise TransformationAdoptionError(
            f"refinement iteration must not be negative: {iteration}"
        )
    return paths.root / "transformation" / f"iteration-{iteration:03d}"


def adopted_transformations(
    paths: RunPaths, iteration: int
) -> AdoptedTransformations | None:
    """What this run already adopted for ``iteration``, or ``None``.

    Read back from the recorded metadata rather than from a directory listing:
    the metadata is what states which files the run adopted, and a stray file
    beside them must not silently become an input to the next stage.
    """
    directory = transformation_dir(paths, iteration)
    metadata_path = directory / METADATA_FILENAME
    if not metadata_path.is_file():
        return None
    metadata = read_json(metadata_path)
    validate_artifact("transformation-adoption", metadata)
    if metadata["run_id"] != paths.root.name:
        raise TransformationAdoptionError(
            "adopted transformation metadata identifies another run: "
            f"{metadata['run_id']}"
        )
    if metadata["iteration"] != iteration:
        raise TransformationAdoptionError(
            "adopted transformation metadata identifies iteration "
            f"{metadata['iteration']}, expected {iteration}"
        )
    # Paths are relative to the run directory: the run carries its own inputs,
    # so reading them back must not depend on where the run tree is mounted.
    adopted: list[Path] = []
    resolved_run = paths.root.resolve()
    expected_directory = directory.resolve()
    for entry in metadata["transformations"]:
        candidate = (resolved_run / entry["path"]).resolve()
        try:
            candidate.relative_to(resolved_run)
        except ValueError as exc:
            raise TransformationAdoptionError(
                f"adopted transformation escapes the run: {entry['path']}"
            ) from exc
        if candidate.parent != expected_directory:
            raise TransformationAdoptionError(
                "adopted transformation is outside its iteration directory: "
                f"{entry['path']}"
            )
        adopted.append(candidate)
    missing = [path for path in adopted if not path.is_file()]
    if missing:
        raise TransformationAdoptionError(
            "the run's adopted transformation is missing: "
            + ", ".join(str(path) for path in missing)
        )
    for path, entry in zip(adopted, metadata["transformations"], strict=True):
        if (
            path.stat().st_size != entry["bytes"]
            or file_sha256(path) != entry["sha256"]
        ):
            raise TransformationAdoptionError(
                f"the run's adopted transformation changed after adoption: {path}"
            )
    return AdoptedTransformations(iteration, directory, tuple(adopted))


def adopt_transformations(
    paths: RunPaths,
    manifest: dict[str, Any],
    sources: Sequence[Path],
    *,
    iteration: int = 0,
) -> AdoptedTransformations | None:
    """Copy ``sources`` into the run once and return the copies.

    Returns ``None`` when there is nothing to adopt, so a stage that selected no
    transformation keeps reporting that fact itself instead of being turned into
    an adoption error.
    """
    existing = adopted_transformations(paths, iteration)
    if not sources:
        return existing

    directory = transformation_dir(paths, iteration)
    directory.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    copies: list[Path] = []
    for source in sorted(Path(source).resolve() for source in sources):
        if not source.is_file():
            raise TransformationAdoptionError(
                f"generated transformation is not a file: {source}"
            )
        target = directory / source.name
        content = source.read_bytes()
        if target.is_file():
            if target.read_bytes() != content:
                raise TransformationAdoptionError(
                    f"iteration {iteration:03d} already adopted a different "
                    f"{source.name}: generation overwrote the run's input"
                )
        else:
            target.write_bytes(content)
        copies.append(target)
        entries.append(
            {
                "path": target.relative_to(paths.root).as_posix(),
                "sha256": file_sha256(target),
                "bytes": len(content),
                "source": _cited_source(source),
            }
        )

    if existing is not None:
        # The metadata is the record of what this iteration judged, so a later
        # stage may not quietly add an input it never mentioned.
        if set(copies) != set(existing.paths):
            raise TransformationAdoptionError(
                f"iteration {iteration:03d} already adopted "
                + ", ".join(sorted(path.name for path in existing.paths))
                + "; refusing to change its inputs"
            )
        return existing

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(manifest.get("run_id") or paths.root.name),
        "language": str(manifest.get("language") or ""),
        "task": str(manifest.get("task") or ""),
        "iteration": iteration,
        # The provider is n8n's choice and never reaches Python, so it is absent
        # rather than guessed; the model and strategy are the run's own axes.
        "model": manifest.get("transformation_model"),
        "strategy": manifest.get("transformation_strategy"),
        "adopted_at": datetime.now(timezone.utc).isoformat(),
        "transformations": entries,
    }
    validate_artifact("transformation-adoption", metadata)
    write_json(directory / METADATA_FILENAME, metadata)
    return AdoptedTransformations(iteration, directory, tuple(copies))


def _cited_source(path: Path) -> str:
    """Where the copy came from, repository-relative whenever it is in the tree."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()
