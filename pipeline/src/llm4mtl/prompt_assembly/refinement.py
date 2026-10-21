"""Assemble the exact prompt, and its recorded request, for refinement iteration N.

This module reads the run's recorded facts through ``run_store`` and
``semantic_tests``, restates the task context the generation received, and
renders the text sent to the refinement model. ``run_store`` only says where
those facts and this output are stored.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm4mtl.artifact_schemas import validate_artifact
from llm4mtl.conventions import default_generated_tests_root, language_config
from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.prompt_assembly.n8n_exports.prompts import PREREQUISITES_SECTION_HEADER
from llm4mtl.prompt_assembly.task_inputs import (
    ResolvedTaskInputs,
    TaskInputResolutionError,
    resolve_custom_task_inputs,
    resolve_task_inputs,
)
from llm4mtl.run_store.attempts import existing_attempts
from llm4mtl.run_store.generations import (
    SEMANTIC_TEST_ARTIFACT,
    SEMANTIC_TEST_GENERATION,
    TRANSFORMATION_ARTIFACT,
    TRANSFORMATION_GENERATION,
    GenerationRecordError,
    prepare_generation_response_directory,
    task_prompt_source,
)
from llm4mtl.run_store.models import RunPaths
from llm4mtl.run_store.responses import recorded_diagnoses
from llm4mtl.run_store.transformations import (
    adopted_transformations,
    suite_id_for_iteration,
)
from llm4mtl.semantic_tests.diagnosis_preparation import (
    diagnosis_reports_location,
    read_failure_reports_for_attempt,
)
from llm4mtl.semantic_tests.suite_execution import OBSERVATION_FILENAME
from llm4mtl.semantic_tests.suites.discovery import CANDIDATES_DIRECTORY
from llm4mtl.serialization.json_io import (
    JsonDocumentConflictError,
    read_json,
    write_json_once_or_match,
)
from llm4mtl.stage_contract import REFERENCE_VALIDATION_FAILED, SYNTAX_INVALID
from llm4mtl.vocabulary import (
    EXECUTION_STAGE_ID,
    EXTRACT_STAGE_ID,
    REFERENCE_VALIDATION_STAGE_ID,
    SYNTAX_VALIDATION_STAGE_ID,
    TECHNICAL_VALIDATION_STAGE_ID,
)

SCHEMA_VERSION = "1.0"
PREPARED_AT = "prepared_at"

# Where the feedback that triggers a refinement comes from.
SYNTAX_FEEDBACK = "syntax"
TECHNICAL_FEEDBACK = "technical"
REFERENCE_FEEDBACK = "reference"
SEMANTIC_FEEDBACK = "semantic"

# Reasons with these prefixes come from executing the suite. A diagnosed reason
# also needs the diagnoses of that execution.
DIAGNOSED_REASON_PREFIX = "DIAGNOSED_"
SEMANTIC_REASON_PREFIXES = (DIAGNOSED_REASON_PREFIX, "SEMANTIC_")
# Every other outcome code (docs/n8n-python-contract.md) is technical feedback.
FEEDBACK_SOURCE_FOR_OUTCOME_CODE = {
    SYNTAX_INVALID: SYNTAX_FEEDBACK,
    REFERENCE_VALIDATION_FAILED: REFERENCE_FEEDBACK,
}
# The stages whose latest recorded attempt each feedback source restates.
STAGES_FOR_FEEDBACK = {
    SYNTAX_FEEDBACK: (SYNTAX_VALIDATION_STAGE_ID,),
    TECHNICAL_FEEDBACK: (EXTRACT_STAGE_ID, TECHNICAL_VALIDATION_STAGE_ID),
    REFERENCE_FEEDBACK: (TECHNICAL_VALIDATION_STAGE_ID, REFERENCE_VALIDATION_STAGE_ID),
    SEMANTIC_FEEDBACK: (SYNTAX_VALIDATION_STAGE_ID, EXECUTION_STAGE_ID),
}

# The assets each prompting strategy gives the generation, as in the master
# workflow's strategy table. Helper methods belong to no strategy. An unknown
# strategy is refused: restating it without assets would silently give the
# refinement a different treatment.
STRATEGY_ASSETS = {
    "only_prompt": frozenset(),
    "grammar": frozenset({"grammar"}),
    "few_shot": frozenset({"examples"}),
    "few_shots_AND_grammar": frozenset({"examples", "grammar"}),
}
# The manifest field that names each artifact type's prompting strategy.
STRATEGY_FIELD = {
    TRANSFORMATION_ARTIFACT: "transformation_strategy",
    SEMANTIC_TEST_ARTIFACT: "test_generation_strategy",
}
# The model files of an extracted semantic-test suite that a refinement restates.
SUITE_MODEL_SUFFIXES = {".json", ".xmi"}

INSTRUCTIONS = {
    TRANSFORMATION_ARTIFACT: (
        "Repair the previous transformation. Preserve behavior unrelated to the "
        "reported defect. Return only the complete corrected transformation."
    ),
    SEMANTIC_TEST_ARTIFACT: (
        "Repair the previous generated semantic test. Preserve valid cases, models, "
        "and assertions unrelated to the reported defect. Return only the complete "
        "corrected file-oriented test response."
    ),
}


class RefinementPreparationError(ValueError):
    """Raised when the preceding artifact or its recorded feedback is absent."""


@dataclass(frozen=True)
class RefinementRequest:
    """What the orchestration asks Python to package for refinement iteration N.

    ``execution_attempt`` names the execution whose failure reports and diagnoses
    enter the prompt. A semantic refinement requires it; every other feedback
    source must leave it unset, because no execution produced that feedback.
    """

    artifact_type: str
    iteration: int
    previous_iteration: int
    provider: str
    model: str
    reason: str
    execution_attempt: int | None = None


def prepare_refinement(
    paths: RunPaths,
    manifest: dict[str, Any],
    request: RefinementRequest,
    *,
    run_diagnoses: Path,
) -> dict[str, Any]:
    """Write the request and exact prompt consumed by refinement iteration N.

    ``run_diagnoses`` is this run's directory in the diagnoses area, resolved by
    the caller through the artifact layout; only the verdicts recorded there for
    ``request.execution_attempt`` enter the prompt.
    """
    _check_request(request)
    payload = _request_payload(paths, manifest, request, Path(run_diagnoses))
    validate_artifact("refinement-request", payload)
    prompt = _render_prompt(payload)
    _prepare_response_directory(paths, request)
    prompt_file = paths.refinement_prompt(request.artifact_type, request.iteration)
    _write_text_once(prompt_file, prompt)
    request_file = paths.refinement_request(request.artifact_type, request.iteration)
    stored = _write_request_once(request_file, payload)
    # Both paths are relative to the run folder: only the caller knows where
    # the run is mounted.
    return {
        "artifact_type": request.artifact_type,
        "iteration": request.iteration,
        "previous_iteration": request.previous_iteration,
        "prompt_file": stored["prompt_file"],
        "request_path": _run_path(paths, request_file),
        "feedback_source": payload["feedback"]["source"],
    }


def _check_request(request: RefinementRequest) -> None:
    if request.iteration != request.previous_iteration + 1 or request.iteration < 1:
        raise RefinementPreparationError(
            "refinement iteration must be exactly previous_iteration + 1"
        )
    if request.artifact_type not in INSTRUCTIONS:
        raise RefinementPreparationError(
            f"unsupported artifact type: {request.artifact_type}"
        )


def _request_payload(
    paths: RunPaths,
    manifest: dict[str, Any],
    request: RefinementRequest,
    run_diagnoses: Path,
) -> dict[str, Any]:
    """The refinement request: task context, previous artifact, and feedback."""
    original_context = _original_task_context(paths, manifest, request.artifact_type)
    previous_files = _previous_artifact_files(
        paths, manifest, request.artifact_type, request.previous_iteration
    )
    feedback = _feedback(paths, manifest, request, run_diagnoses)
    prompt_file = paths.refinement_prompt(request.artifact_type, request.iteration)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": paths.root.name,
        "task": str(manifest["task"]),
        "language": str(manifest["language"]),
        "artifact_type": request.artifact_type,
        "iteration": request.iteration,
        "previous_iteration": request.previous_iteration,
        "execution_attempt": request.execution_attempt,
        "provider": request.provider,
        "model": request.model,
        "original_task_context": original_context,
        "previous_artifact": {"files": previous_files},
        "feedback": feedback,
        "instruction": INSTRUCTIONS[request.artifact_type],
        "prompt_file": _run_path(paths, prompt_file),
        PREPARED_AT: datetime.now(timezone.utc).isoformat(),
    }


def _prepare_response_directory(paths: RunPaths, request: RefinementRequest) -> None:
    """Create the directory the refinement's generation writes into."""
    try:
        prepare_generation_response_directory(
            paths, artifact_type=request.artifact_type, iteration=request.iteration
        )
    except (GenerationRecordError, OSError) as exc:
        raise RefinementPreparationError(
            f"cannot prepare {request.artifact_type} generation directory for "
            f"iteration {request.iteration:03d}: {exc}"
        ) from exc


def _write_request_once(request_file: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Write the request once; a retry must prepare the same request."""
    try:
        return write_json_once_or_match(
            request_file,
            payload,
            comparable=_without_time,
            check_stored=_validate_request,
        )
    except JsonDocumentConflictError as exc:
        raise RefinementPreparationError(
            f"refinement request already exists with different content: {request_file}"
        ) from exc


def _validate_request(request: dict[str, Any]) -> None:
    validate_artifact("refinement-request", request)


def _original_task_context(
    paths: RunPaths, manifest: dict[str, Any], artifact_type: str
) -> dict[str, Any]:
    """The task context the generation received, restated for the refinement."""
    language = str(manifest["language"])
    try:
        context = _task_context(paths, language, str(manifest["task"]))
    except TaskInputResolutionError as exc:
        raise RefinementPreparationError(str(exc)) from exc
    return {
        "prompt": _text_artifact(task_prompt_source(paths, manifest)),
        "metamodels": [
            _text_artifact(REPO_ROOT / metamodel.path)
            for metamodel in context.metamodels
        ],
        "supporting_files": _supporting_context(
            language, artifact_type, manifest, context.grammar.path
        ),
        **_generation_only_context(artifact_type, context),
    }


def _task_context(paths: RunPaths, language: str, task: str) -> ResolvedTaskInputs:
    """The prompt inputs to restate: the run's own custom-task metamodel if it
    has one, otherwise the contract's files."""
    if paths.metamodel.is_file():
        return resolve_custom_task_inputs(
            language,
            task,
            paths.metamodel.read_text(encoding="utf-8"),
            metamodel_path=_artifact_path(paths.metamodel),
        )
    return resolve_task_inputs(language, task)


def _artifact_path(path: Path) -> str:
    """Repository-relative when the run is inside the repository, else absolute.
    Both forms resolve against ``REPO_ROOT``."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _supporting_context(
    language: str,
    artifact_type: str,
    manifest: dict[str, Any],
    grammar_path: str,
) -> list[dict[str, Any]]:
    """The strategy-selected files the generation received beside the task."""
    assets = _strategy_assets(artifact_type, manifest)
    supporting = _supporting_files(language, artifact_type, assets, grammar_path)
    missing = [path for path in supporting if not path.is_file()]
    if missing:
        raise RefinementPreparationError(
            "refinement context is missing: " + ", ".join(str(path) for path in missing)
        )
    return [_text_artifact(path) for path in supporting]


def _strategy_assets(artifact_type: str, manifest: dict[str, Any]) -> frozenset[str]:
    strategy_field = STRATEGY_FIELD[artifact_type]
    strategy = str(manifest.get(strategy_field) or "")
    assets = STRATEGY_ASSETS.get(strategy)
    if assets is None:
        raise RefinementPreparationError(
            f"unknown {strategy_field} {strategy!r}: cannot restate which "
            "assets the generation received"
        )
    return assets


def _supporting_files(
    language: str, artifact_type: str, assets: frozenset[str], grammar_path: str
) -> list[Path]:
    """The asset files, in the order the generation prompt lists them."""
    files: list[Path] = []
    if artifact_type == SEMANTIC_TEST_ARTIFACT:
        files.append(
            TARGET.prompt_assets
            / "tests"
            / "contract"
            / language
            / "semantic_cases_contract.txt"
        )
    if "examples" in assets:
        files.append(_few_shot_examples(language, artifact_type))
    if "grammar" in assets:
        files.append(REPO_ROOT / grammar_path)
    return files


def _few_shot_examples(language: str, artifact_type: str) -> Path:
    if artifact_type == SEMANTIC_TEST_ARTIFACT:
        return (
            TARGET.prompt_assets
            / "tests"
            / "few_shot"
            / language
            / "test_generation_examples.txt"
        )
    return (
        TARGET.prompt_assets / "transformations" / "few_shot" / language / "Examples.txt"
    )


def _generation_only_context(
    artifact_type: str, context: ResolvedTaskInputs
) -> dict[str, Any]:
    """The task inputs one generation kind states beside the prompt and metamodels.

    A transformation request names the contract's namespace URIs. A
    semantic-test request carries the specifications of the prerequisite
    Reactions tasks. Refinement restates the same, and leaves out a key the
    task has nothing for.
    """
    if artifact_type == TRANSFORMATION_ARTIFACT and context.metamodel_uris:
        return {"metamodel_uris": list(context.metamodel_uris)}
    if artifact_type == SEMANTIC_TEST_ARTIFACT and context.prerequisite_prompts:
        return {
            "prerequisite_prompts": [
                _text_artifact(REPO_ROOT / prompt.path)
                for prompt in context.prerequisite_prompts
            ]
        }
    return {}


def _previous_artifact_files(
    paths: RunPaths, manifest: dict[str, Any], artifact_type: str, iteration: int
) -> list[dict[str, Any]]:
    """The artifact the refinement repairs, as text files."""
    if artifact_type == TRANSFORMATION_ARTIFACT:
        candidates = _previous_transformation_files(paths, manifest, iteration)
    else:
        candidates = _previous_semantic_test_files(paths, manifest, iteration)
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise RefinementPreparationError(
            f"previous {artifact_type} iteration {iteration:03d} is missing"
        )
    return [_text_artifact(path) for path in existing]


def _previous_transformation_files(
    paths: RunPaths, manifest: dict[str, Any], iteration: int
) -> list[Path]:
    """The run's adopted copy, or else the raw generated response."""
    adopted = adopted_transformations(paths, iteration)
    if adopted is not None and adopted.paths:
        return list(adopted.paths)
    suffix = language_config(str(manifest["language"])).language_key
    return [
        paths.generation_response(
            TRANSFORMATION_GENERATION, iteration, f"{manifest['task']}.{suffix}"
        )
    ]


def _previous_semantic_test_files(
    paths: RunPaths, manifest: dict[str, Any], iteration: int
) -> list[Path]:
    """The raw generated response, then the model files of its extracted suite."""
    task = str(manifest["task"])
    response = paths.generation_response(
        SEMANTIC_TEST_GENERATION, iteration, f"{task}.md"
    )
    suite = (
        default_generated_tests_root(language_config(str(manifest["language"])))
        / task
        / CANDIDATES_DIRECTORY
        / _suite_location(paths, manifest, iteration)
    )
    if not suite.is_dir():
        return [response]
    return [
        response,
        *(
            path
            for path in sorted(suite.rglob("*"))
            if path.is_file() and path.suffix.lower() in SUITE_MODEL_SUFFIXES
        ),
    ]


def _suite_location(paths: RunPaths, manifest: dict[str, Any], iteration: int) -> Path:
    """``<model>/<strategy>/<suite-id>`` of the suite generated in ``iteration``."""
    return (
        Path(str(manifest.get("test_generation_model") or ""))
        / str(manifest.get("test_generation_strategy") or "")
        / suite_id_for_iteration(paths.root.name, iteration)
    )


def _feedback(
    paths: RunPaths,
    manifest: dict[str, Any],
    request: RefinementRequest,
    run_diagnoses: Path,
) -> dict[str, Any]:
    """The recorded facts that say what is wrong with the previous artifact."""
    source = _feedback_source(request.reason)
    execution_attempt = request.execution_attempt
    _check_execution_attempt(source, execution_attempt)
    failure_reports = _failure_reports(paths, manifest, request, source)
    diagnoses = (
        _diagnosis_facts(run_diagnoses, execution_attempt)
        if execution_attempt is not None
        else []
    )
    _check_feedback_found(request, source, failure_reports, diagnoses)
    return {
        "source": source,
        "reason": request.reason,
        "stage_facts": _stage_facts(paths, source, execution_attempt),
        "failure_reports": failure_reports,
        "diagnoses": diagnoses,
    }


def _feedback_source(reason: str) -> str:
    if reason.startswith(SEMANTIC_REASON_PREFIXES):
        return SEMANTIC_FEEDBACK
    return FEEDBACK_SOURCE_FOR_OUTCOME_CODE.get(reason, TECHNICAL_FEEDBACK)


def _check_execution_attempt(source: str, execution_attempt: int | None) -> None:
    """Only a semantic refinement names the execution its feedback came from."""
    if source == SEMANTIC_FEEDBACK and execution_attempt is None:
        raise RefinementPreparationError(
            "semantic refinement requires the execution attempt that produced it"
        )
    if source != SEMANTIC_FEEDBACK and execution_attempt is not None:
        raise RefinementPreparationError(
            f"{source} refinement must not name an execution attempt"
        )


def _failure_reports(
    paths: RunPaths,
    manifest: dict[str, Any],
    request: RefinementRequest,
    source: str,
) -> list[dict[str, Any]]:
    if request.execution_attempt is not None:
        return _failure_report_facts(paths, request.execution_attempt)
    if source == REFERENCE_FEEDBACK:
        return _reference_failure_facts(paths, manifest, request.previous_iteration)
    return []


def _check_feedback_found(
    request: RefinementRequest,
    source: str,
    failure_reports: list[dict[str, Any]],
    diagnoses: list[dict[str, Any]],
) -> None:
    """Refuse a semantic refinement whose execution left nothing to repair."""
    if source == SEMANTIC_FEEDBACK and not failure_reports:
        raise RefinementPreparationError(
            f"execution attempt {request.execution_attempt} has no failure reports"
        )
    if request.reason.startswith(DIAGNOSED_REASON_PREFIX) and not diagnoses:
        raise RefinementPreparationError(
            f"execution attempt {request.execution_attempt} has no matching diagnoses"
        )


def _stage_facts(
    paths: RunPaths, source: str, execution_attempt: int | None
) -> list[dict[str, Any]]:
    """The latest recorded attempt of each stage behind ``source``.

    For semantic feedback the execution stage is the selected attempt.
    """
    facts: list[dict[str, Any]] = []
    for stage in STAGES_FOR_FEEDBACK[source]:
        attempts = existing_attempts(paths.stage_attempts_dir(stage))
        if not attempts:
            continue
        attempt = (
            execution_attempt
            if stage == EXECUTION_STAGE_ID and execution_attempt is not None
            else max(attempts)
        )
        if attempt not in attempts:
            raise RefinementPreparationError(
                f"no recorded {stage} attempt {attempt} exists"
            )
        facts.append(_stage_fact(paths, stage, attempt))
    if not facts:
        raise RefinementPreparationError(f"no recorded {source} feedback exists")
    return facts


def _stage_fact(paths: RunPaths, stage: str, attempt: int) -> dict[str, Any]:
    result_path = paths.stage_attempt_result(stage, attempt)
    evidence_path = paths.stage_attempt_evidence(stage, attempt)
    result = read_json(result_path) if result_path.is_file() else {}
    evidence = read_json(evidence_path) if evidence_path.is_file() else {}
    return {
        "stage": stage,
        "attempt": attempt,
        "status": result.get("status"),
        "outcome_code": result.get("outcome_code"),
        "counts": result.get("counts", {}),
        "details": evidence.get("details", {}),
    }


def _failure_report_facts(
    paths: RunPaths, execution_attempt: int
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for indexed in read_failure_reports_for_attempt(paths.root, execution_attempt):
        report = indexed.payload
        facts.append(
            {
                "report": indexed.reference,
                "identity": report.get("identity"),
                "failure": report.get("failure"),
                "source_diagnosis": report.get("source_diagnosis"),
            }
        )
    return facts


def _reference_failure_facts(
    paths: RunPaths, manifest: dict[str, Any], previous_iteration: int
) -> list[dict[str, Any]]:
    """Why the reference rejected the previous suite, as a failure fact.

    Reference validation stores its verdict as a suite observation, not as a
    failure report. It is read here so the prompt shows what disagreed with the
    reference; without it the model has nothing to repair.
    """
    path = (
        paths.observations_dir
        / str(manifest["task"])
        / _suite_location(paths, manifest, previous_iteration)
        / OBSERVATION_FILENAME
    )
    if not path.is_file():
        return []
    payload = read_json(path)
    validate_artifact("suite-execution", payload)
    observation = dict(payload.get("observation") or {})
    if observation.get("reference_valid"):
        return []
    return [_reference_failure_fact(paths, path, payload, observation)]


def _reference_failure_fact(
    paths: RunPaths,
    path: Path,
    payload: dict[str, Any],
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report": _run_path(paths, path),
        "identity": {
            "task": payload.get("task"),
            "suite_id": payload.get("suite_id"),
        },
        "failure": {
            "failure_stage": observation.get("failure_stage"),
            "error_summary": observation.get("error_summary"),
            "assertions_evaluated": observation.get("assertions_evaluated"),
            "assertions_passed": observation.get("assertions_passed"),
        },
    }


def _diagnosis_facts(
    run_diagnoses: Path, execution_attempt: int
) -> list[dict[str, Any]]:
    """The diagnoses recorded for the failure reports of one execution attempt."""
    facts: list[dict[str, Any]] = []
    evidence_prefix = f"{diagnosis_reports_location(execution_attempt)}/"
    for path in recorded_diagnoses(Path(run_diagnoses)):
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
    return (
        "\n\n".join(
            [
                "# Original task\n" + context["prompt"]["content"],
                "# Relevant metamodel/context\n"
                + "\n\n".join(
                    f"## {entry['path']}\n{entry['content']}"
                    for entry in context["metamodels"] + context["supporting_files"]
                ),
                *_metamodel_uris_section(context),
                *_prerequisites_section(context),
                "# CURRENT ARTIFACT\n"
                + "\n\n".join(
                    f"## {entry['path']}\n{entry['content']}" for entry in previous
                ),
                "# FEEDBACK\n```json\n"
                + json.dumps(payload["feedback"], indent=2, ensure_ascii=False)
                + "\n```",
                "# Refinement instruction\n" + payload["instruction"],
            ]
        )
        + "\n"
    )


def _prerequisites_section(context: dict[str, Any]) -> list[str]:
    prompts = context.get("prerequisite_prompts") or []
    if not prompts:
        return []
    return [
        f"# {PREREQUISITES_SECTION_HEADER}\n"
        + "\n\n".join(f"## {entry['path']}\n{entry['content']}" for entry in prompts)
    ]


def _metamodel_uris_section(context: dict[str, Any]) -> list[str]:
    uris = context.get("metamodel_uris") or []
    if not uris:
        return []
    return [
        "# Metamodel namespace URIs for this task\n"
        + "\n".join(f"- {uri}" for uri in uris)
    ]


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
    comparable = {key: value for key, value in payload.items() if key != PREPARED_AT}
    # Older schema 1.0 requests may lack ``execution_attempt``; that means the
    # same as the explicit ``None`` that is written now.
    comparable.setdefault("execution_attempt", None)
    return comparable
