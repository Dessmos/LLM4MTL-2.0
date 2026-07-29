"""Provenance recorded in the immutable run manifest.

A derived metric is only reproducible if the run states which code, contracts,
and tooling produced it. This module collects the facts that are known at run
creation: the exact code state, renderer, runtime tools, and hand-authored input
artifacts. Mutation operator and qualification-corpus versions are added by the
batches that introduce those artifacts.

The git revision is mandatory: a run that cannot name the code that produced it
is not reproducible, so run creation fails instead of recording an unknown.
"""

from __future__ import annotations

import platform
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from llm4mtl import run_store
from llm4mtl.experiment_store.models import SCHEMA_VERSION as EXPERIMENT_SCHEMA_VERSION
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.stage_contract import SCHEMA_VERSION as STAGE_SCHEMA_VERSION

GIT_COMMAND_TIMEOUT_SECONDS = 15
TOOL_COMMAND_TIMEOUT_SECONDS = 15


class ProvenanceError(RuntimeError):
    """Raised when a mandatory provenance fact cannot be determined."""


def build_provenance(language: str, task: str, **extra: Any) -> dict[str, Any]:
    """Collect the provenance block for a run manifest.

    Extra keyword arguments are merged in, so a caller can record facts only it
    knows (for example the resolved-config hash of a local runner invocation).
    """
    from llm4mtl.languages import UnsupportedLanguageError, language_adapter

    try:
        adapter = language_adapter(language)
        renderer_version = adapter.renderer_version
        language_tool_versions = adapter.runtime_tool_versions()
    except UnsupportedLanguageError as exc:
        raise ProvenanceError(str(exc)) from exc

    return {
        "git_commit": git_commit(),
        "git_dirty": is_working_tree_dirty(),
        "renderer_version": renderer_version,
        "schema_versions": {
            "run_store": run_store.SCHEMA_VERSION,
            "stage_contract": STAGE_SCHEMA_VERSION,
            "experiment_store": EXPERIMENT_SCHEMA_VERSION,
        },
        "tool_versions": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "java": required_tool_version("java", ("java", "-version")),
            "maven": required_tool_version("Maven", ("mvn", "--version")),
            **language_tool_versions,
        },
        "input_hashes": input_hashes(language, task),
        **extra,
    }


def input_hashes(language: str, task: str) -> dict[str, Any]:
    """Content hashes of the hand-authored inputs that decide this run's outcome.

    The reference transformation is the behavioural oracle, the task contract
    fixes the model bindings, and the metamodels define what the assertions can
    even refer to. A result that does not name them cannot be reproduced, and a
    silent edit to any of them would change the experiment without changing any
    recorded identity.

    These inputs are mandatory for a supported task. Missing one aborts run
    creation: recording ``null`` would create evidence that cannot be tied to
    the behavioural oracle and structural contract that produced it.
    """
    from llm4mtl.conventions import (
        default_references_root,
        default_task_contracts_root,
        language_config,
    )
    from llm4mtl.task_contracts import load_task_contract
    from llm4mtl.transformation_execution.hashing import file_sha256

    try:
        config = language_config(language)
    except KeyError as exc:
        raise ProvenanceError(str(exc)) from exc

    reference = next(default_references_root(config).glob(f"{task}.*"), None)
    contract_path = default_task_contracts_root(config) / f"{task}.json"
    contract = load_task_contract(task, contracts_root=default_task_contracts_root(config), config=config)
    if reference is None:
        raise ProvenanceError(f"reference transformation not found for {language}/{task}")
    if not contract_path.is_file() or contract is None:
        raise ProvenanceError(f"task contract not found for {language}/{task}")

    metamodels: dict[str, str] = {}
    for model in contract.models:
        if not model.metamodel_file:
            continue
        path = _metamodel_path(config.language_key, model.metamodel_file)
        metamodels[path.relative_to(REPO_ROOT).as_posix()] = file_sha256(path)

    return {
        "reference_transformation": file_sha256(reference),
        "task_contract": file_sha256(contract_path),
        "metamodels": metamodels,
    }


def _metamodel_path(language: str, recorded_path: str) -> Path:
    """Resolve a legacy contract path to its protected benchmark input."""
    filename = Path(recorded_path).name
    language_directory = f"{language.upper()}_model"
    candidates = (
        TARGET.benchmark / "metamodels" / language / filename,
        TARGET.benchmark / "metamodels" / "additional_models" / language_directory / filename,
        TARGET.benchmark / "metamodels" / filename,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ProvenanceError(
        f"metamodel {filename!r} from the {language} task contract was not found "
        "under benchmark/metamodels"
    )


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
        raise ProvenanceError(f"cannot determine the git working-tree state of {REPO_ROOT}")
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
