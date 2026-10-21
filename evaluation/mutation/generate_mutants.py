"""Generate deterministic text-replacement mutants from a frozen JSON spec."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from evaluation._common import EvaluationInputError, read_json_object, write_csv
from llm4mtl.languages import language_adapter
from llm4mtl.paths import REPO_ROOT


CATALOG_FIELDS = (
    "mutant_id",
    "language",
    "task",
    "operator",
    "operator_set_version",
    "reference_path",
    "mutant_path",
    "source_hash",
    "mutant_hash",
    "syntactic_validity",
    "executable",
    "observable",
    "qualified",
)


def generate_mutants(
    specification: Mapping[str, Any],
    output_root: Path,
) -> list[dict[str, str]]:
    """Apply every exact replacement and return an unqualified catalog."""
    version = specification.get("operator_set_version")
    definitions = specification.get("mutants")
    if not isinstance(version, str) or not version:
        raise EvaluationInputError("mutation spec needs operator_set_version")
    if not isinstance(definitions, list) or not definitions:
        raise EvaluationInputError("mutation spec needs a non-empty mutants list")
    output_root = output_root.resolve()
    rows: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for raw in definitions:
        if not isinstance(raw, dict):
            raise EvaluationInputError("each mutation definition must be an object")
        row = _generate_one(raw, version, output_root)
        if row["mutant_id"] in seen_ids:
            raise EvaluationInputError(f"duplicate mutant_id: {row['mutant_id']}")
        seen_ids.add(row["mutant_id"])
        rows.append(row)
    return rows


def _generate_one(
    definition: Mapping[str, Any],
    version: str,
    output_root: Path,
) -> dict[str, str]:
    required = ("mutant_id", "language", "task", "operator", "find", "replacement")
    missing = [field for field in required if not isinstance(definition.get(field), str)]
    if missing:
        raise EvaluationInputError(
            "mutation definition misses string fields: " + ", ".join(missing)
        )
    mutant_id = str(definition["mutant_id"])
    if not mutant_id or Path(mutant_id).name != mutant_id:
        raise EvaluationInputError(f"invalid mutant_id: {mutant_id!r}")
    language = str(definition["language"]).lower()
    task = str(definition["task"])
    adapter = language_adapter(language)
    reference = adapter.reference_transformation(task).resolve()
    declared_reference = definition.get("reference")
    if declared_reference is not None:
        candidate = (REPO_ROOT / str(declared_reference)).resolve()
        if candidate != reference:
            raise EvaluationInputError(
                f"{mutant_id}: declared reference is not the adapter reference for "
                f"{language}/{task}"
            )
    if not reference.is_file():
        raise EvaluationInputError(f"{mutant_id}: reference does not exist: {reference}")
    source_bytes = reference.read_bytes()
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvaluationInputError(
            f"{mutant_id}: reference is not UTF-8 text: {reference}"
        ) from exc
    needle = str(definition["find"])
    replacement = str(definition["replacement"])
    if not needle:
        raise EvaluationInputError(f"{mutant_id}: find must not be empty")
    occurrences = source.count(needle)
    requested = definition.get("occurrence")
    if requested is None:
        if occurrences != 1:
            raise EvaluationInputError(
                f"{mutant_id}: find occurs {occurrences} times; set occurrence explicitly"
            )
        occurrence = 1
    elif isinstance(requested, int) and not isinstance(requested, bool) and requested > 0:
        occurrence = requested
        if occurrence > occurrences:
            raise EvaluationInputError(
                f"{mutant_id}: occurrence {occurrence} exceeds {occurrences} matches"
            )
    else:
        raise EvaluationInputError(f"{mutant_id}: occurrence must be a positive integer")
    mutated = _replace_occurrence(source, needle, replacement, occurrence)
    if mutated == source:
        raise EvaluationInputError(f"{mutant_id}: mutation does not change the source")
    destination = output_root / language / task / f"{mutant_id}{reference.suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    mutant_bytes = mutated.encode("utf-8")
    destination.write_bytes(mutant_bytes)
    return {
        "mutant_id": mutant_id,
        "language": language,
        "task": task,
        "operator": str(definition["operator"]),
        "operator_set_version": version,
        "reference_path": _portable_path(reference),
        "mutant_path": _portable_path(destination),
        "source_hash": _sha256(source_bytes),
        "mutant_hash": _sha256(mutant_bytes),
        "syntactic_validity": "",
        "executable": "",
        "observable": "",
        "qualified": "",
    }


def _replace_occurrence(source: str, needle: str, replacement: str, occurrence: int) -> str:
    start = -1
    search_from = 0
    for _ in range(occurrence):
        start = source.find(needle, search_from)
        search_from = start + len(needle)
    return source[:start] + replacement + source[start + len(needle) :]


def _portable_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = generate_mutants(read_json_object(args.spec), args.output_root)
    write_csv(args.catalog, CATALOG_FIELDS, rows)
    print(f"generated {len(rows)} mutants and wrote {args.catalog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
