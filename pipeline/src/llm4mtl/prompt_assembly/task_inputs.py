"""Resolve the exact repository inputs for one task prompt.

The task contract is the only mapping from a reference transformation to its
metamodel files.  Callers receive the reference, those exact metamodels, and the
language grammar; the raw contract is intentionally not included in the LLM
input.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import ArtifactSchemaError, validate_artifact
from llm4mtl.conventions import (
    default_task_contracts_root,
    language_config,
)
from llm4mtl.paths import REPO_ROOT, TARGET

TASK_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class TaskInputResolutionError(ValueError):
    """Raised when a task contract cannot resolve to safe, existing inputs."""


@dataclass(frozen=True)
class PromptInputFile:
    """One UTF-8 source file supplied to the prompt-generation LLM."""

    path: str
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "content": self.content}


@dataclass(frozen=True)
class ResolvedTaskInputs:
    """The task-specific prompt inputs selected through one task contract."""

    language: str
    task: str
    contract_path: str
    reference: PromptInputFile
    metamodels: tuple[PromptInputFile, ...]
    grammar: PromptInputFile

    @property
    def metamodel_text(self) -> str:
        return "\n\n".join(
            f"### {metamodel.path}\n{metamodel.content}"
            for metamodel in self.metamodels
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "task": self.task,
            "contract_path": self.contract_path,
            "reference": self.reference.to_dict(),
            "metamodels": [
                metamodel.to_dict() for metamodel in self.metamodels
            ],
            "metamodel_text": self.metamodel_text,
            "grammar": self.grammar.to_dict(),
        }


def resolve_task_inputs(language: str, task: str) -> ResolvedTaskInputs:
    """Resolve ``reference -> task contract -> exact metamodel files``.

    All persisted paths must be repository-relative and remain inside the
    protected benchmark tree.  A missing or stale path fails the request rather
    than falling back to a language-wide glob.
    """
    if not TASK_NAME.fullmatch(task):
        raise TaskInputResolutionError(f"invalid task name: {task!r}")

    try:
        config = language_config(language)
    except KeyError as exc:
        raise TaskInputResolutionError(str(exc)) from exc

    language_key = config.language_key
    contract_path = default_task_contracts_root(config) / f"{task}.json"
    if not contract_path.is_file():
        raise TaskInputResolutionError(
            f"task contract not found for {language_key}/{task}"
        )

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        validate_artifact("contract", contract)
    except (json.JSONDecodeError, ArtifactSchemaError) as exc:
        raise TaskInputResolutionError(
            f"invalid task contract for {language_key}/{task}: {exc}"
        ) from exc

    if contract.get("task") != task:
        raise TaskInputResolutionError(
            f"task contract identity mismatch: expected {task!r}, "
            f"found {contract.get('task')!r}"
        )
    recorded_language = contract.get("language")
    if recorded_language is not None and recorded_language != language_key:
        raise TaskInputResolutionError(
            f"task contract language mismatch: expected {language_key!r}, "
            f"found {recorded_language!r}"
        )

    reference_path = _protected_path(
        contract.get("reference"),
        field="reference",
        required_root=TARGET.benchmark / "tasks" / language_key / "references",
    )
    expected_transformation = contract.get("transformation")
    if reference_path.name != expected_transformation:
        raise TaskInputResolutionError(
            "contract reference does not match its transformation: "
            f"{reference_path.name!r} != {expected_transformation!r}"
        )

    metamodel_paths: list[Path] = []
    for model in contract["models"]:
        recorded_path = model.get("metamodelFile")
        if recorded_path is None:
            continue
        metamodel_path = _protected_path(
            recorded_path,
            field=f"models[{model['runtimeName']}].metamodelFile",
            required_root=TARGET.benchmark / "metamodels",
        )
        if metamodel_path not in metamodel_paths:
            metamodel_paths.append(metamodel_path)

    grammar_path = (
        TARGET.prompt_assets
        / "transformations"
        / "grammar"
        / language_key
        / "EBNF.txt"
    )
    if not grammar_path.is_file():
        raise TaskInputResolutionError(
            f"grammar not found for language {language_key!r}"
        )

    return ResolvedTaskInputs(
        language=language_key,
        task=task,
        contract_path=_relative_path(contract_path),
        reference=_read_input(reference_path),
        metamodels=tuple(_read_input(path) for path in metamodel_paths),
        grammar=_read_input(grammar_path),
    )


def _protected_path(
    recorded_path: object,
    *,
    field: str,
    required_root: Path,
) -> Path:
    if not isinstance(recorded_path, str) or not recorded_path:
        raise TaskInputResolutionError(f"{field} must be a repository-relative path")
    candidate = Path(recorded_path)
    if candidate.is_absolute():
        raise TaskInputResolutionError(f"{field} must not be absolute")

    resolved = (REPO_ROOT / candidate).resolve()
    allowed_root = required_root.resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise TaskInputResolutionError(
            f"{field} escapes {allowed_root.relative_to(REPO_ROOT)}"
        ) from exc
    if not resolved.is_file():
        raise TaskInputResolutionError(
            f"{field} does not exist: {candidate.as_posix()}"
        )
    return resolved


def _read_input(path: Path) -> PromptInputFile:
    return PromptInputFile(
        path=_relative_path(path),
        content=path.read_text(encoding="utf-8"),
    )


def _relative_path(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()
