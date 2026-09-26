"""Provenance recorded in the immutable run manifest.

A derived metric is only reproducible if the run states which code, contracts,
and tooling produced it. This module collects the facts that are known at run
creation: the exact code state, renderer, runtime tools, and hand-authored input
artifacts. Mutation operator and qualification-corpus versions are not recorded
yet.

The git revision is mandatory: a run that cannot name the code that produced it
is not reproducible, so run creation fails instead of recording an unknown.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from llm4mtl import run_store
from llm4mtl.conventions import (
    LanguageConfig,
    default_references_root,
    default_task_contracts_root,
    frozen_task_prompt,
    language_config,
)
from llm4mtl.languages import UnsupportedLanguageError, language_adapter
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.task_inputs import CUSTOM_METAMODEL_PATH
from llm4mtl.serialization.hashing import file_sha256
from llm4mtl.stage_contract import SCHEMA_VERSION as STAGE_SCHEMA_VERSION
from llm4mtl.task_contracts import TaskContract, load_task_contract

GIT_COMMAND_TIMEOUT_SECONDS = 15
TOOL_COMMAND_TIMEOUT_SECONDS = 15
# Recorded when a run reads user-supplied text instead of a benchmark input.
CUSTOM_SOURCE = "custom"


class ProvenanceError(RuntimeError):
    """Raised when a mandatory provenance fact cannot be determined."""


def build_provenance(
    language: str,
    task: str,
    *,
    custom_task_prompt: str | None = None,
    custom_task_metamodel: str | None = None,
) -> dict[str, Any]:
    """Collect the provenance block for a run manifest.

    ``custom_task_prompt`` is the user-authored prompt a run reads instead of
    the frozen benchmark prompt, and ``custom_task_metamodel`` the metamodel it
    reads instead of the ones a task contract names; each is hashed in place of
    the input it replaces.
    """
    renderer_version, language_tool_versions = _language_facts(language)
    return {
        "git_commit": git_commit(),
        "git_dirty": is_working_tree_dirty(),
        "renderer_version": renderer_version,
        "schema_versions": {
            "run_store": run_store.SCHEMA_VERSION,
            "stage_contract": STAGE_SCHEMA_VERSION,
        },
        "tool_versions": _tool_versions(language_tool_versions),
        "input_hashes": input_hashes(
            language,
            task,
            custom_task_prompt=custom_task_prompt,
            custom_task_metamodel=custom_task_metamodel,
        ),
    }


def _tool_versions(language_tool_versions: dict[str, str]) -> dict[str, str]:
    """The versions of the runtime and tools every language needs, plus its own."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "java": required_tool_version("java", ("java", "-version")),
        "maven": required_tool_version("Maven", ("mvn", "--version")),
        **language_tool_versions,
    }


def _language_facts(language: str) -> tuple[str, dict[str, str]]:
    """The renderer version and runtime tool versions of one language."""
    try:
        adapter = language_adapter(language)
        return adapter.renderer_version, adapter.runtime_tool_versions()
    except UnsupportedLanguageError as exc:
        raise ProvenanceError(str(exc)) from exc


def input_hashes(
    language: str,
    task: str,
    *,
    custom_task_prompt: str | None = None,
    custom_task_metamodel: str | None = None,
) -> dict[str, Any]:
    """Content hashes of the hand-authored inputs that decide this run's outcome.

    The reference transformation is the behavioural oracle, the task contract
    fixes the model bindings, and the metamodels define what the assertions can
    refer to. Without their hashes a silent edit to any of them would change the
    experiment without changing any recorded identity.

    For a benchmark task these inputs are mandatory: a missing one raises
    :class:`ProvenanceError` instead of recording ``null``.

    A custom task prompt replaces the frozen prompt, and a custom task metamodel
    replaces the contract's metamodels. ``task_prompt`` and ``metamodels`` then
    hash the text the run was given. A run with a custom metamodel has no
    reference or contract, so those are recorded as null.
    """
    config = _language_config(language)
    if custom_task_metamodel is not None:
        return _custom_task_hashes(
            language, task, custom_task_prompt, custom_task_metamodel
        )
    hashes = _benchmark_input_hashes(config, language, task)
    if custom_task_prompt is not None:
        return {
            **hashes,
            "task_prompt": _text_sha256(custom_task_prompt),
            "task_prompt_source": CUSTOM_SOURCE,
        }
    return {**hashes, "task_prompt": _frozen_task_prompt_hash(config, task)}


def _language_config(language: str) -> LanguageConfig:
    try:
        return language_config(language)
    except KeyError as exc:
        raise ProvenanceError(str(exc)) from exc


def _custom_task_hashes(
    language: str, task: str, prompt: str | None, metamodel: str
) -> dict[str, Any]:
    """Hashes of a task the user wrote: its prompt and metamodel, nothing else."""
    if prompt is None:
        raise ProvenanceError(
            f"custom task metamodel without a custom task prompt: {language}/{task}"
        )
    return {
        "reference_transformation": None,
        "task_contract": None,
        "metamodels": {CUSTOM_METAMODEL_PATH: _text_sha256(metamodel)},
        "task_prompt": _text_sha256(prompt),
        "task_prompt_source": CUSTOM_SOURCE,
        "metamodel_source": CUSTOM_SOURCE,
    }


def _benchmark_input_hashes(
    config: LanguageConfig, language: str, task: str
) -> dict[str, Any]:
    """Hashes of the task's reference, task contract, and contract metamodels."""
    reference = next(default_references_root(config).glob(f"{task}.*"), None)
    contract_path = default_task_contracts_root(config) / f"{task}.json"
    contract = load_task_contract(
        task, contracts_root=default_task_contracts_root(config), config=config
    )
    if reference is None:
        raise ProvenanceError(
            f"reference transformation not found for {language}/{task}"
        )
    if not contract_path.is_file() or contract is None:
        raise ProvenanceError(f"task contract not found for {language}/{task}")
    return {
        "reference_transformation": file_sha256(reference),
        "task_contract": file_sha256(contract_path),
        "metamodels": _metamodel_hashes(config, contract),
    }


def _metamodel_hashes(config: LanguageConfig, contract: TaskContract) -> dict[str, str]:
    """Hash of each metamodel file the contract names, by repository path."""
    metamodels: dict[str, str] = {}
    for model in contract.models:
        if not model.metamodel_file:
            continue
        path = _metamodel_path(config.language_key, model.metamodel_file)
        metamodels[path.relative_to(REPO_ROOT).as_posix()] = file_sha256(path)
    return metamodels


def _frozen_task_prompt_hash(config: LanguageConfig, task: str) -> str:
    task_prompt = frozen_task_prompt(config, task)
    if not task_prompt.is_file():
        raise ProvenanceError(
            f"frozen task prompt not found for {config.language_key}/{task}"
        )
    return file_sha256(task_prompt)


def _text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _metamodel_path(language: str, recorded_path: str) -> Path:
    """Resolve the contract's exact repository-relative metamodel path."""
    recorded = Path(recorded_path)
    if recorded.is_absolute():
        raise ProvenanceError(
            f"absolute metamodel path in the {language} task contract: {recorded}"
        )
    candidate = (REPO_ROOT / recorded).resolve()
    metamodel_root = (TARGET.benchmark / "metamodels").resolve()
    try:
        candidate.relative_to(metamodel_root)
    except ValueError as exc:
        raise ProvenanceError(
            f"metamodel path in the {language} task contract escapes "
            "benchmark/metamodels"
        ) from exc
    if not candidate.is_file():
        raise ProvenanceError(
            f"metamodel path from the {language} task contract does not exist: "
            f"{recorded.as_posix()}"
        )
    return candidate


@lru_cache(maxsize=1)
def git_commit() -> str:
    """The revision of the working tree, or raise when it cannot be determined."""
    completed = _run_git(["rev-parse", "HEAD"])
    if completed is None or completed.returncode != 0:
        raise ProvenanceError(
            f"cannot determine the git revision of {REPO_ROOT}; "
            "experiment runs require a git checkout so results stay reproducible"
        )
    return completed.stdout.strip()


def is_working_tree_dirty() -> bool:
    """True when tracked or untracked, non-ignored files differ from the revision."""
    completed = _run_git(["status", "--porcelain", "--untracked-files=normal"])
    if completed is None or completed.returncode != 0:
        raise ProvenanceError(
            f"cannot determine the git working-tree state of {REPO_ROOT}"
        )
    return bool(completed.stdout.strip())


@lru_cache(maxsize=None)
def required_tool_version(label: str, command: tuple[str, ...]) -> str:
    """The first version line of a required runtime tool."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=TOOL_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProvenanceError(f"cannot determine {label} version") from exc
    output = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode != 0 or not output:
        raise ProvenanceError(f"cannot determine {label} version")
    return output.splitlines()[0].strip()


def _run_git(arguments: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
