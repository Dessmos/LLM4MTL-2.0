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
from llm4mtl.paths import REPO_ROOT, TARGET, require_repository_relative
from llm4mtl.transformation_execution.hashing import file_sha256

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
    metamodel_uris: tuple[str, ...]
    grammar: PromptInputFile
    prerequisite_prompts: tuple[PromptInputFile, ...] = ()

    @property
    def metamodel_text(self) -> str:
        return "\n\n".join(
            f"### {metamodel.path}\n{metamodel.content}"
            for metamodel in self.metamodels
        )

    @property
    def metamodel_uri_text(self) -> str:
        """The namespace URIs a generated transformation must reference.

        These come from the contract, so a prompt cannot state a namespace the
        task does not use. Transformation prompts used to hardcode one Vitruv
        URI for every language, which was wrong for ETL and ATL.
        """
        return "\n".join(f"- {uri}" for uri in self.metamodel_uris)

    @property
    def prerequisite_prompt_text(self) -> str:
        """The specifications of the tasks this one presupposes.

        A test has to build its pre-state through changes something reacts to.
        Which changes those are is decided by the other tasks that run beside
        this one, and their specifications say it in the same words as this
        task's own -- so they are handed over rather than left to be guessed.
        """
        return "\n\n".join(
            f"### {prompt.path}\n{prompt.content}"
            for prompt in self.prerequisite_prompts
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "task": self.task,
            "contract_path": self.contract_path,
            "reference": self.reference.to_dict(),
            "metamodels": [metamodel.to_dict() for metamodel in self.metamodels],
            "metamodel_text": self.metamodel_text,
            "metamodel_uris": list(self.metamodel_uris),
            "metamodel_uri_text": self.metamodel_uri_text,
            "grammar": self.grammar.to_dict(),
            "prerequisite_prompts": [
                prompt.to_dict() for prompt in self.prerequisite_prompts
            ],
            "prerequisite_prompt_text": self.prerequisite_prompt_text,
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

    contract = _load_task_contract(contract_path, language_key, task)
    _validate_contract_identity(contract, language_key, task)

    reference_path = _protected_path(
        contract.get("reference"),
        field="reference",
        required_root=TARGET.benchmark / "tasks" / language_key / "references",
    )
    _validate_reference_identity(contract, reference_path, language_key, task)
    metamodel_paths, metamodel_uris = _contract_metamodels(contract)

    grammar_path = (
        TARGET.prompt_assets / "transformations" / "grammar" / language_key / "EBNF.txt"
    )
    if not grammar_path.is_file():
        raise TaskInputResolutionError(
            f"grammar not found for language {language_key!r}"
        )

    return ResolvedTaskInputs(
        language=language_key,
        task=task,
        contract_path=require_repository_relative(contract_path),
        reference=_read_input(reference_path),
        metamodels=tuple(_read_input(path) for path in metamodel_paths),
        metamodel_uris=tuple(metamodel_uris),
        grammar=_read_input(grammar_path),
        prerequisite_prompts=_prerequisite_prompts(language_key, contract, config),
    )


def _prerequisite_prompts(
    language: str,
    contract: dict[str, Any],
    config: Any,
) -> tuple[PromptInputFile, ...]:
    """Task specifications of the prerequisites, prerequisites first."""
    contracts_root = default_task_contracts_root(config)
    prompts_root = TARGET.prompt_assets / "task_prompts" / language
    ordered: list[str] = []

    def walk(task: str, seen: tuple[str, ...]) -> None:
        if task in seen:
            raise TaskInputResolutionError(f"prerequisite cycle through {task!r}")
        path = contracts_root / f"{task}.json"
        if not path.is_file():
            return
        payload = json.loads(path.read_text(encoding="utf-8"))
        for name in payload.get("prerequisiteTasks") or ():
            walk(str(name), (*seen, task))
            if name not in ordered:
                ordered.append(str(name))

    walk(str(contract["task"]), ())
    return tuple(
        _read_input(prompts_root / f"{name}.txt")
        for name in ordered
        if (prompts_root / f"{name}.txt").is_file()
    )


def _load_task_contract(
    contract_path: Path, language: str, task: str
) -> dict[str, Any]:
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        validate_artifact("contract", contract)
    except (json.JSONDecodeError, ArtifactSchemaError) as exc:
        raise TaskInputResolutionError(
            f"invalid task contract for {language}/{task}: {exc}"
        ) from exc
    return contract


def _validate_contract_identity(
    contract: dict[str, Any], language: str, task: str
) -> None:
    if contract.get("task") != task:
        raise TaskInputResolutionError(
            f"task contract identity mismatch: expected {task!r}, "
            f"found {contract.get('task')!r}"
        )
    # Every contract records its own language, so this check applies to every
    # language rather than being skipped for whichever ones omitted the field.
    recorded_language = contract.get("language")
    if recorded_language != language:
        raise TaskInputResolutionError(
            f"task contract language mismatch: expected {language!r}, "
            f"found {recorded_language!r}"
        )


def _validate_reference_identity(
    contract: dict[str, Any], reference_path: Path, language: str, task: str
) -> None:
    expected_transformation = contract.get("transformation")
    if reference_path.name != expected_transformation:
        raise TaskInputResolutionError(
            "contract reference does not match its transformation: "
            f"{reference_path.name!r} != {expected_transformation!r}"
        )

    # The contract records the hash of the reference it was derived from. An
    # edited reference therefore invalidates its contract loudly here.
    recorded_hash = contract.get("sourceHash")
    actual_hash = file_sha256(reference_path)
    if recorded_hash != actual_hash:
        raise TaskInputResolutionError(
            f"task contract is stale for {language}/{task}: "
            f"reference hash {actual_hash} does not match recorded "
            f"{recorded_hash}. Rebuild it with "
            "python -m llm4mtl.task_contracts.build_language_task_contracts "
            f"--language {language}"
        )


def _contract_metamodels(
    contract: dict[str, Any],
) -> tuple[list[Path], list[str]]:
    metamodel_paths: list[Path] = []
    metamodel_uris: list[str] = []
    for model in contract["models"]:
        recorded_uri = model.get("metamodelUri")
        if recorded_uri and recorded_uri not in metamodel_uris:
            metamodel_uris.append(str(recorded_uri))
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
    return metamodel_paths, metamodel_uris


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
        path=require_repository_relative(path),
        content=path.read_text(encoding="utf-8"),
    )
