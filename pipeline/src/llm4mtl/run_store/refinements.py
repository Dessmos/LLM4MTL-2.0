"""Prepare compact, immutable inputs for feedback-guided refinement."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.conventions import default_generated_tests_root, frozen_task_prompt, language_config
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.task_inputs import (
    TaskInputResolutionError,
    resolve_task_inputs,
)
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.generations import (
    GenerationRecordError,
    prepare_generation_response_directory,
)
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.transformations import adopted_transformations
from llm4mtl.semantic_tests.diagnosis_preparation import (
    read_failure_reports_for_attempt,
)
from llm4mtl.serialization.json_io import read_json, write_json_once

SCHEMA_VERSION = "1.0"
REQUEST_FILENAME = "request.json"
PROMPT_FILENAME = "prompt.md"
STAGE_FOR_REASON = {
    "TEST_SPEC_INVALID": "extract",
    "TECH_COMPILE_FAILED": "technical-validation",
    "TECH_EXEC_FAILED": "technical-validation",
    "REFERENCE_VALIDATION_FAILED": "reference-validation",
    "SYNTAX_INVALID": "syntax-validation",
}


class RefinementPreparationError(ValueError):
    """Raised when the preceding artifact or its recorded feedback is absent."""


def prepare_refinement(
    paths: RunPaths,
    manifest: dict[str, Any],
    *,
    artifact_type: str,
    iteration: int,
    previous_iteration: int,
    provider: str,
    model: str,
    reason: str,
    diagnoses_root: Path,
    execution_attempt: int | None = None,
) -> dict[str, Any]:
    """Write the request and exact prompt consumed by refinement iteration N."""
    if iteration != previous_iteration + 1 or iteration < 1:
        raise RefinementPreparationError(
            "refinement iteration must be exactly previous_iteration + 1"
        )
    if artifact_type not in {"transformation", "semantic-test"}:
        raise RefinementPreparationError(f"unsupported artifact type: {artifact_type}")

    language = str(manifest["language"])
    task = str(manifest["task"])
    try:
        context = resolve_task_inputs(language, task)
    except TaskInputResolutionError as exc:
        raise RefinementPreparationError(str(exc)) from exc
    prompt_path = frozen_task_prompt(language_config(language), task)
    original_context = {
        "prompt": _text_artifact(prompt_path),
        "metamodels": [
            _text_artifact(REPO_ROOT / metamodel.path) for metamodel in context.metamodels
        ],
        "supporting_files": _supporting_context(
            language, artifact_type, manifest, context.grammar.path
        ),
    }
    previous_files = _previous_artifact_files(
        paths, manifest, artifact_type, previous_iteration
    )
    source = _feedback_source(reason)
    if source == "semantic" and execution_attempt is None:
        raise RefinementPreparationError(
            "semantic refinement requires the execution attempt that produced it"
        )
    if source != "semantic" and execution_attempt is not None:
        raise RefinementPreparationError(
            f"{source} refinement must not name an execution attempt"
        )
    failure_reports = (
        _failure_report_facts(paths, execution_attempt)
        if execution_attempt is not None
        else []
    )
    diagnoses = (
        _diagnosis_facts(paths, diagnoses_root, execution_attempt)
        if execution_attempt is not None
        else []
    )
    if source == "semantic" and not failure_reports:
        raise RefinementPreparationError(
            f"execution attempt {execution_attempt} has no failure reports"
        )
    if reason.startswith("DIAGNOSED_") and not diagnoses:
        raise RefinementPreparationError(
            f"execution attempt {execution_attempt} has no matching diagnoses"
        )
    feedback = {
        "source": source,
        "reason": reason,
        "stage_facts": _stage_facts(paths, source, execution_attempt),
        "failure_reports": failure_reports,
        "diagnoses": diagnoses,
    }
    instruction = (
        "Repair the previous transformation. Preserve behavior unrelated to the "
        "reported defect. Return only the complete corrected transformation."
        if artifact_type == "transformation"
        else "Repair the previous generated semantic test. Preserve valid cases, models, "
        "and assertions unrelated to the reported defect. Return only the complete "
        "corrected file-oriented test response."
    )
    directory = paths.refinement_dir(artifact_type, iteration)
    request_path = directory / REQUEST_FILENAME
    rendered_prompt_path = directory / PROMPT_FILENAME
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": paths.root.name,
        "task": task,
        "language": language,
        "artifact_type": artifact_type,
        "iteration": iteration,
        "previous_iteration": previous_iteration,
        "execution_attempt": execution_attempt,
        "provider": provider,
        "model": model,
        "original_task_context": original_context,
        "previous_artifact": {"files": previous_files},
        "feedback": feedback,
        "instruction": instruction,
        "prompt_file": _run_path(paths, rendered_prompt_path),
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }
    validate_artifact("refinement-request", payload)
    prompt = _render_prompt(payload)
    try:
        prepare_generation_response_directory(
            paths, artifact_type=artifact_type, iteration=iteration
        )
    except (GenerationRecordError, OSError) as exc:
        raise RefinementPreparationError(
            f"cannot prepare {artifact_type} generation directory for "
            f"iteration {iteration:03d}: {exc}"
        ) from exc
    _write_text_once(rendered_prompt_path, prompt)
    try:
        write_json_once(request_path, payload)
    except FileExistsError:
        existing = read_json(request_path)
        validate_artifact("refinement-request", existing)
        if _without_time(existing) != _without_time(payload):
            raise RefinementPreparationError(
                f"refinement request already exists with different content: {request_path}"
            )
        payload = existing
    return {
        "artifact_type": artifact_type,
        "iteration": iteration,
        "previous_iteration": previous_iteration,
        "prompt_path": f"/data/artifacts/runs/{paths.root.name}/{payload['prompt_file']}",
        "request_path": _run_path(paths, request_path),
        "feedback_source": source,
    }


def _previous_artifact_files(
    paths: RunPaths, manifest: dict[str, Any], artifact_type: str, iteration: int
) -> list[dict[str, Any]]:
    task = str(manifest["task"])
    if artifact_type == "transformation":
        adopted = adopted_transformations(paths, iteration)
        candidates = list(adopted.paths) if adopted is not None else []
        if not candidates:
            suffix = language_config(str(manifest["language"])).language_key
            candidates = [
                paths.generation_response("transformation-generation", iteration, f"{task}.{suffix}")
            ]
    else:
        candidates = [
            paths.generation_response("semantic-test-generation", iteration, f"{task}.md")
        ]
        suite = (
            default_generated_tests_root(language_config(str(manifest["language"])))
            / task
            / "candidates"
            / str(manifest.get("test_generation_model") or "")
            / str(manifest.get("test_generation_strategy") or "")
            / f"{paths.root.name}_{iteration:03d}"
        )
        if suite.is_dir():
            candidates.extend(
                path for path in sorted(suite.rglob("*"))
                if path.is_file() and path.suffix.lower() in {".json", ".xmi"}
            )
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RefinementPreparationError(
            f"previous {artifact_type} iteration {iteration:03d} is missing"
        )
    return [_text_artifact(path) for path in existing]


def _feedback_source(reason: str) -> str:
    if reason.startswith("DIAGNOSED_") or reason.startswith("SEMANTIC_"):
        return "semantic"
    stage = STAGE_FOR_REASON.get(reason)
    if stage == "syntax-validation":
        return "syntax"
    if stage == "reference-validation":
        return "reference"
    return "technical"


def _supporting_context(
    language: str,
    artifact_type: str,
    manifest: dict[str, Any],
    grammar_path: str,
) -> list[dict[str, Any]]:
    strategy_field = (
        "transformation_strategy"
        if artifact_type == "transformation"
        else "test_generation_strategy"
    )
    strategy = str(manifest.get(strategy_field) or "")
    supporting: list[Path] = []
    if artifact_type == "semantic-test":
        supporting.append(
            TARGET.prompt_assets
            / "tests"
            / "contract"
            / language
            / "semantic_cases_contract.txt"
        )
        if "few_shot" in strategy:
            supporting.append(
                TARGET.prompt_assets
                / "tests"
                / "few_shot"
                / language
                / "test_generation_examples.txt"
            )
    elif "few_shot" in strategy:
        supporting.append(
            TARGET.prompt_assets
            / "transformations"
            / "few_shot"
            / language
            / "Examples.txt"
        )
    if "grammar" in strategy:
        supporting.append(REPO_ROOT / grammar_path)
    missing = [path for path in supporting if not path.is_file()]
    if missing:
        raise RefinementPreparationError(
            "refinement context is missing: " + ", ".join(str(path) for path in missing)
        )
    return [_text_artifact(path) for path in supporting]


def _stage_facts(
    paths: RunPaths, source: str, execution_attempt: int | None
) -> list[dict[str, Any]]:
    stages = {
        "syntax": ("syntax-validation",),
        "technical": ("extract", "technical-validation"),
        "reference": ("technical-validation", "reference-validation"),
        "semantic": ("syntax-validation", "execution"),
    }[source]
    facts: list[dict[str, Any]] = []
    for stage in stages:
        attempts = existing_attempts(paths.stage_attempts_dir(stage))
        if not attempts:
            continue
        attempt = (
            execution_attempt
            if stage == "execution" and execution_attempt is not None
            else max(attempts)
        )
        if attempt not in attempts:
            raise RefinementPreparationError(
                f"no recorded {stage} attempt {attempt} exists"
            )
        result_path = paths.stage_attempt_result(stage, attempt)
        evidence_path = paths.stage_attempt_evidence(stage, attempt)
        result = read_json(result_path) if result_path.is_file() else {}
        evidence = read_json(evidence_path) if evidence_path.is_file() else {}
        facts.append({
            "stage": stage,
            "attempt": attempt,
            "status": result.get("status"),
            "outcome_code": result.get("outcome_code"),
            "counts": result.get("counts", {}),
            "details": evidence.get("details", {}),
        })
    if not facts:
        raise RefinementPreparationError(f"no recorded {source} feedback exists")
    return facts


def _failure_report_facts(
    paths: RunPaths, execution_attempt: int
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for indexed in read_failure_reports_for_attempt(paths.root, execution_attempt):
        report = indexed.payload
        facts.append({
            "report": indexed.reference,
            "identity": report.get("identity"),
            "failure": report.get("failure"),
            "source_diagnosis": report.get("source_diagnosis"),
        })
    return facts


def _diagnosis_facts(
    paths: RunPaths, diagnoses_root: Path, execution_attempt: int
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    run_root = Path(diagnoses_root) / paths.root.name
    evidence_prefix = (
        f"diagnosis/execution/attempt-{execution_attempt:03d}/reports/"
    )
    for path in sorted(run_root.glob("attempt-*/diagnosis.json")):
        diagnosis = read_json(path)
        if not str(diagnosis.get("evidence_ref") or "").startswith(evidence_prefix):
            continue
        validate_artifact("diagnosis", diagnosis)
        facts.append(diagnosis)
    return facts


def _text_artifact(path: Path) -> dict[str, Any]:
    content = Path(path).read_text(encoding="utf-8")
    return {
        "path": _cited_path(Path(path)),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
    }


def _render_prompt(payload: dict[str, Any]) -> str:
    context = payload["original_task_context"]
    previous = payload["previous_artifact"]["files"]
    return "\n\n".join([
        "# Original task\n" + context["prompt"]["content"],
        "# Relevant metamodel/context\n" + "\n\n".join(
            f"## {entry['path']}\n{entry['content']}" for entry in context["metamodels"]
            + context["supporting_files"]
        ),
        "# CURRENT ARTIFACT\n" + "\n\n".join(
            f"## {entry['path']}\n{entry['content']}" for entry in previous
        ),
        "# FEEDBACK\n```json\n" + json.dumps(payload["feedback"], indent=2, ensure_ascii=False) + "\n```",
        "# Refinement instruction\n" + payload["instruction"],
    ]) + "\n"


def _write_text_once(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding="utf-8") != content:
            raise RefinementPreparationError(
                f"refinement prompt already exists with different content: {path}"
            )


def _run_path(paths: RunPaths, path: Path) -> str:
    return Path(path).resolve().relative_to(paths.root.resolve()).as_posix()


def _cited_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _without_time(payload: dict[str, Any]) -> dict[str, Any]:
    comparable = {
        key: value for key, value in payload.items() if key != "prepared_at"
    }
    # The selector was added compatibly to schema 1.0. An old non-semantic
    # request omitted it; that is equivalent to the explicit null new writers use.
    comparable.setdefault("execution_attempt", None)
    return comparable
