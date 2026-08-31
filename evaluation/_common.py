"""Shared input validation for the standalone evaluation scripts."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from llm4mtl.paths import REPO_ROOT


REQUIRED_EXPERIMENT_FIELDS = (
    "max_test_refinement_iterations",
    "max_transformation_refinement_iterations",
    "parser_feedback",
    "semantic_feedback",
    "source_diagnosis",
)


class EvaluationInputError(ValueError):
    """Raised before evaluation when selected artifacts are incomplete."""


@dataclass(frozen=True)
class SelectedRun:
    """One fully preflighted run selected for an evaluation campaign."""

    run_id: str
    root: Path
    manifest: Mapping[str, Any]
    terminal_result: Mapping[str, Any]

    @property
    def language(self) -> str:
        return str(self.manifest["language"])

    @property
    def task(self) -> str:
        return str(self.manifest["task"])


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object with an error that names the offending artifact."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvaluationInputError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationInputError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluationInputError(f"expected a JSON object in {path}")
    return payload


def read_run_ids(path: Path) -> tuple[str, ...]:
    """Read the frozen campaign run list, ignoring blank/comment lines."""
    try:
        run_ids = tuple(
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    except OSError as exc:
        raise EvaluationInputError(f"cannot read run list {path}: {exc}") from exc
    if not run_ids:
        raise EvaluationInputError(f"run list is empty: {path}")
    if len(set(run_ids)) != len(run_ids):
        raise EvaluationInputError(f"run list contains duplicate ids: {path}")
    for run_id in run_ids:
        if Path(run_id).name != run_id:
            raise EvaluationInputError(f"invalid run id in {path}: {run_id!r}")
    return run_ids


def preflight_runs(runs_root: Path, run_ids_path: Path) -> tuple[SelectedRun, ...]:
    """Fail the entire evaluation start unless every selected run is complete.

    Legacy runs without ``experiment_config`` are deliberately rejected. They
    remain useful for debugging but cannot enter a controlled campaign.
    """
    runs_root = runs_root.resolve()
    selected: list[SelectedRun] = []
    errors: list[str] = []
    for run_id in read_run_ids(run_ids_path):
        run_root = runs_root / run_id
        manifest_path = run_root / "manifest.json"
        terminal_path = run_root / "result.json"
        try:
            if not manifest_path.is_file():
                raise EvaluationInputError("manifest.json is missing")
            manifest = read_json_object(manifest_path)
            _validate_manifest(run_id, manifest)
            if not terminal_path.is_file():
                raise EvaluationInputError("terminal result.json is missing")
            terminal = read_json_object(terminal_path)
            _validate_terminal_result(run_id, terminal)
            _validate_transformation_iterations(run_root, manifest, terminal)
            selected.append(SelectedRun(run_id, run_root, manifest, terminal))
        except EvaluationInputError as exc:
            errors.append(f"{run_id}: {exc}")
    if errors:
        raise EvaluationInputError(
            "evaluation preflight failed; no run was evaluated:\n- "
            + "\n- ".join(errors)
        )
    return tuple(selected)


def transformation_iterations(selected_run: SelectedRun) -> tuple[tuple[int, Path], ...]:
    """Return each stored transformation iteration from its authoritative metadata."""
    iterations: list[tuple[int, Path]] = []
    transformation_root = selected_run.root / "transformation"
    for directory in sorted(transformation_root.glob("iteration-*")):
        if not directory.is_dir():
            continue
        metadata = read_json_object(directory / "metadata.json")
        try:
            iteration = int(metadata["iteration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise EvaluationInputError(
                f"invalid transformation iteration in {directory / 'metadata.json'}"
            ) from exc
        if directory.name != f"iteration-{iteration:03d}":
            raise EvaluationInputError(
                f"transformation metadata iteration does not match directory {directory}"
            )
        for field, expected in (
            ("run_id", selected_run.run_id),
            ("language", selected_run.language),
            ("task", selected_run.task),
        ):
            if metadata.get(field) != expected:
                raise EvaluationInputError(
                    f"{directory / 'metadata.json'} has {field}={metadata.get(field)!r}, "
                    f"expected {expected!r}"
                )
        records = metadata.get("transformations")
        if not isinstance(records, list) or len(records) != 1:
            raise EvaluationInputError(
                f"{directory / 'metadata.json'} must identify exactly one transformation"
            )
        record = records[0]
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise EvaluationInputError(
                f"invalid transformation record in {directory / 'metadata.json'}"
            )
        path = REPO_ROOT / str(record["path"])
        # Stored paths are repository-relative in current artifacts. If a future
        # producer stores a run-relative path, resolve that unambiguous fallback.
        if not path.is_file():
            path = selected_run.root / str(record["path"])
        if not path.is_file():
            raise EvaluationInputError(
                f"stored transformation does not exist: {record['path']}"
            )
        try:
            path.resolve().relative_to(selected_run.root.resolve())
        except ValueError as exc:
            raise EvaluationInputError(
                f"stored transformation is outside its run directory: {path}"
            ) from exc
        recorded_hash = record.get("sha256")
        if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
            raise EvaluationInputError(
                f"stored transformation has no valid sha256: {record['path']}"
            )
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != recorded_hash:
            raise EvaluationInputError(
                f"stored transformation hash mismatch: {record['path']}"
            )
        iterations.append((iteration, path.resolve()))
    if not iterations:
        raise EvaluationInputError(
            f"no stored transformation iterations in {transformation_root}"
        )
    return tuple(iterations)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    """Write one derived CSV only after its complete row set is available."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a derived or campaign-input CSV with stable string values."""
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))
    except OSError as exc:
        raise EvaluationInputError(f"cannot read CSV {path}: {exc}") from exc


def parse_bool(value: object, *, field: str) -> bool:
    """Parse an explicit CSV boolean; blank/unknown is never false."""
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise EvaluationInputError(f"{field} must be true or false, got {value!r}")


def _validate_manifest(run_id: str, manifest: Mapping[str, Any]) -> None:
    if manifest.get("run_id") != run_id:
        raise EvaluationInputError(
            f"manifest run_id is {manifest.get('run_id')!r}, expected {run_id!r}"
        )
    for field in ("language", "task", "pipeline_variant"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise EvaluationInputError(f"manifest field {field!r} is missing")
    config = manifest.get("experiment_config")
    if not isinstance(config, dict):
        raise EvaluationInputError("manifest experiment_config is missing")
    missing = [field for field in REQUIRED_EXPERIMENT_FIELDS if field not in config]
    if missing:
        raise EvaluationInputError(
            "manifest experiment_config misses: " + ", ".join(missing)
        )
    for field in REQUIRED_EXPERIMENT_FIELDS[:2]:
        value = config[field]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > 3
        ):
            raise EvaluationInputError(
                f"manifest experiment_config.{field} must be an integer from 0 to 3"
            )
    for field in REQUIRED_EXPERIMENT_FIELDS[2:]:
        if not isinstance(config[field], bool):
            raise EvaluationInputError(
                f"manifest experiment_config.{field} must be boolean"
            )


def _validate_terminal_result(run_id: str, terminal: Mapping[str, Any]) -> None:
    if terminal.get("run_id") != run_id:
        raise EvaluationInputError(
            f"result run_id is {terminal.get('run_id')!r}, expected {run_id!r}"
        )
    if terminal.get("status") not in {
        "completed",
        "completed_with_failures",
        "failed",
        "incomplete",
    }:
        raise EvaluationInputError("result.json has no recognized terminal status")
    if not isinstance(terminal.get("terminal_state"), str):
        raise EvaluationInputError("result.json has no terminal_state")
    if not isinstance(terminal.get("recorded_at"), str):
        raise EvaluationInputError("result.json has no recorded_at timestamp")


def _validate_transformation_iterations(
    run_root: Path,
    manifest: Mapping[str, Any],
    terminal: Mapping[str, Any],
) -> None:
    selected = SelectedRun(run_root.name, run_root, manifest, terminal)
    iterations = transformation_iterations(selected)
    numbers = [iteration for iteration, _ in iterations]
    expected = list(range(numbers[-1] + 1))
    if numbers != expected:
        raise EvaluationInputError(
            f"transformation iterations must be contiguous from 0, found {numbers}"
        )
    budget = int(manifest["experiment_config"]["max_transformation_refinement_iterations"])
    if numbers[-1] > budget:
        raise EvaluationInputError(
            f"stored transformation iteration {numbers[-1]} exceeds configured budget {budget}"
        )
    reported_final = terminal.get("transformation_iteration")
    if isinstance(reported_final, int) and reported_final != numbers[-1]:
        raise EvaluationInputError(
            f"result.json reports transformation_iteration={reported_final}, "
            f"but final stored iteration is {numbers[-1]}"
        )
