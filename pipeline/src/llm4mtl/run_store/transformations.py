"""The run's own copy of every transformation it judged.

Generation writes its raw response into the run. The first stage that judges
it *adopts* it: copies it once into the run as an immutable input. Every later
stage of the same iteration judges that copy, and evidence, manifests and
evaluation cite it.

Refinement regenerates the transformation, so the copy is per refinement
iteration::

    <run-dir>/transformation/iteration-000/<Task>.<ext>
    <run-dir>/transformation/iteration-000/metadata.json

The file keeps its task name because the execution stage pairs a suite with a
transformation by that stem; renaming it to ``generated.etl`` would silently
produce zero execution pairs.

Adoption is idempotent and write-once. Re-running a stage of the same iteration
finds identical bytes and reuses the copy. Different bytes under the same
iteration mean generation overwrote the input mid-run, so adoption refuses them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.paths import REPO_ROOT
from llm4mtl.run_store.models import RunPaths, iteration_dir_name
from llm4mtl.serialization.hashing import file_sha256
from llm4mtl.serialization.json_io import (
    JsonDocumentConflictError,
    read_json,
    write_json_once_or_match,
)

SCHEMA_VERSION = "1.0"
METADATA_FILENAME = "metadata.json"
ADOPTED_AT = "adopted_at"
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


def suite_id_for_iteration(run_id: str, iteration: int) -> str:
    """The suite id the master workflow gives a run's suite in ``iteration``."""
    return f"{run_id}_{iteration:03d}"


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
    return paths.root / "transformation" / iteration_dir_name(iteration)


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
    _check_metadata_identity(paths, iteration, metadata)
    entries = metadata["transformations"]
    adopted = [_adopted_path(paths, directory, entry["path"]) for entry in entries]
    _check_adopted_files_unchanged(adopted, entries)
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
    entries = [
        _adopt_file(paths, directory, source, iteration)
        for source in sorted(Path(source).resolve() for source in sources)
    ]
    copies = tuple(paths.root / entry["path"] for entry in entries)

    if existing is not None:
        _check_same_inputs(existing, copies, iteration)
        return existing
    _write_metadata_once(paths, manifest, iteration, entries)
    return AdoptedTransformations(iteration, directory, copies)


def _check_metadata_identity(
    paths: RunPaths, iteration: int, metadata: dict[str, Any]
) -> None:
    """Refuse metadata that is invalid or describes another run or iteration."""
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


def _adopted_path(paths: RunPaths, directory: Path, recorded: str) -> Path:
    """Resolve one recorded path; it must stay in the iteration directory.

    Paths are relative to the run directory: the run carries its own inputs,
    so reading them back must not depend on where the run tree is mounted.
    """
    resolved_run = paths.root.resolve()
    candidate = (resolved_run / recorded).resolve()
    try:
        candidate.relative_to(resolved_run)
    except ValueError as exc:
        raise TransformationAdoptionError(
            f"adopted transformation escapes the run: {recorded}"
        ) from exc
    if candidate.parent != directory.resolve():
        raise TransformationAdoptionError(
            "adopted transformation is outside its iteration directory: "
            f"{recorded}"
        )
    return candidate


def _check_adopted_files_unchanged(
    adopted: list[Path], entries: list[dict[str, Any]]
) -> None:
    """Refuse adopted files that are missing or changed since adoption."""
    missing = [path for path in adopted if not path.is_file()]
    if missing:
        raise TransformationAdoptionError(
            "the run's adopted transformation is missing: "
            + ", ".join(str(path) for path in missing)
        )
    for path, entry in zip(adopted, entries, strict=True):
        if (
            path.stat().st_size != entry["bytes"]
            or file_sha256(path) != entry["sha256"]
        ):
            raise TransformationAdoptionError(
                f"the run's adopted transformation changed after adoption: {path}"
            )


def _adopt_file(
    paths: RunPaths, directory: Path, source: Path, iteration: int
) -> dict[str, Any]:
    """Copy one source into the iteration directory, once; return its entry."""
    if not source.is_file():
        raise TransformationAdoptionError(
            f"generated transformation is not a file: {source}"
        )
    target = directory / source.name
    content = source.read_bytes()
    if not target.is_file():
        target.write_bytes(content)
    elif target.read_bytes() != content:
        raise TransformationAdoptionError(
            f"iteration {iteration:03d} already adopted a different "
            f"{source.name}: generation overwrote the run's input"
        )
    return {
        "path": target.relative_to(paths.root).as_posix(),
        "sha256": file_sha256(target),
        "bytes": len(content),
        "source": _cited_source(source),
    }


def _check_same_inputs(
    existing: AdoptedTransformations, copies: tuple[Path, ...], iteration: int
) -> None:
    """Refuse a later stage that adopts other files than the first one did.

    The metadata records what this iteration judged, so a later stage may not
    quietly add an input it never mentioned.
    """
    if set(copies) != set(existing.paths):
        raise _changed_inputs_error(existing.paths, iteration)


def _write_metadata_once(
    paths: RunPaths,
    manifest: dict[str, Any],
    iteration: int,
    entries: list[dict[str, Any]],
) -> None:
    """Record the adoption; a concurrent adoption must record the same files."""
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(manifest.get("run_id") or paths.root.name),
        "language": str(manifest.get("language") or ""),
        "task": str(manifest.get("task") or ""),
        "iteration": iteration,
        # No provider: it is n8n's choice, stated only in the generation record,
        # so it is left out rather than guessed. Model and strategy are run axes.
        "model": manifest.get("transformation_model"),
        "strategy": manifest.get("transformation_strategy"),
        ADOPTED_AT: datetime.now(timezone.utc).isoformat(),
        "transformations": entries,
    }
    validate_artifact("transformation-adoption", metadata)
    try:
        write_json_once_or_match(
            transformation_dir(paths, iteration) / METADATA_FILENAME,
            metadata,
            comparable=_without_adopted_at,
        )
    except JsonDocumentConflictError as exc:
        stored_entries = exc.stored["transformations"]
        stored_paths = [paths.root / entry["path"] for entry in stored_entries]
        raise _changed_inputs_error(stored_paths, iteration) from exc


def _changed_inputs_error(
    adopted: Sequence[Path], iteration: int
) -> TransformationAdoptionError:
    return TransformationAdoptionError(
        f"iteration {iteration:03d} already adopted "
        + ", ".join(sorted(path.name for path in adopted))
        + "; refusing to change its inputs"
    )


def _without_adopted_at(metadata: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != ADOPTED_AT}


def _cited_source(path: Path) -> str:
    """Where the copy came from, repository-relative whenever it is in the tree."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()
