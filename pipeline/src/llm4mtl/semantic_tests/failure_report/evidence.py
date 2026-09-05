"""The facts both report types resolve from one recorded execution.

Identity, the generated inputs and their recorded hashes, the stage evidence,
the parser verdict, the observation, the reference result, and the task context
are the same questions whichever report is being assembled. They are answered
once here so the two builders cannot answer them differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llm4mtl.paths import TARGET
from llm4mtl.semantic_tests.failure_report.artifacts import (
    _json_artifact,
    _read_object,
    _text_artifact,
)
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.models import (
    GENERATED_EXECUTION_LABEL,
    RUN_ID_PATTERN,
)
from llm4mtl.semantic_tests.failure_report.request import _input_path
from llm4mtl.serialization.hashing import directory_sha256, file_sha256


def _identity(manifest: dict[str, Any], attempt: int) -> dict[str, Any]:
    # Only the axes the report itself resolves paths from are mandatory. A run
    # may deliberately record a null model axis — that is what `exactly_one`
    # writes when the run fixes no value for it, as an explicitly named
    # transformation does — and refusing the report then would make a whole
    # legitimate run undiagnosable over a provenance field the report only
    # copies. The null is carried through as the null it is.
    required = ("run_id", "task", "language")
    missing = [field for field in required if not isinstance(manifest.get(field), str)]
    if missing:
        raise FailureReportError(
            f"manifest is missing string identity fields: {', '.join(missing)}"
        )
    run_id = str(manifest["run_id"])
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise FailureReportError(f"invalid run_id in manifest: {run_id!r}")
    return {
        "run_id": run_id,
        "task_id": manifest["task"],
        "language": manifest["language"],
        "model": manifest.get("transformation_model"),
        "attempt": attempt,
        "transformation_model": manifest.get("transformation_model"),
        "test_generation_model": manifest.get("test_generation_model"),
        "transformation_strategy": manifest.get("transformation_strategy"),
        "test_generation_strategy": manifest.get("test_generation_strategy"),
    }


def _read_execution(path: Path, identity: dict[str, Any], label: str) -> dict[str, Any]:
    payload = _read_object(path, label)
    expected = {
        "language": identity["language"],
        "task": identity["task_id"],
    }
    mismatches = [
        f"{field}={payload.get(field)!r}, expected {value!r}"
        for field, value in expected.items()
        if payload.get(field) != value
    ]
    if mismatches:
        raise FailureReportError(f"{label} identity mismatch: {'; '.join(mismatches)}")
    _observation(payload, label)
    return payload


def _generated_inputs(execution: dict[str, Any]) -> tuple[Path, Path]:
    inputs = execution.get("inputs")
    if not isinstance(inputs, dict):
        raise FailureReportError("generated execution has no inputs object")
    suite = inputs.get("suite")
    transformation = inputs.get("transformation")
    if not isinstance(suite, dict) or suite.get("role") != "generated_suite":
        raise FailureReportError(
            "generated execution does not identify a generated suite"
        )
    if (
        not isinstance(transformation, dict)
        or transformation.get("role") != "generated_transformation"
    ):
        raise FailureReportError(
            "generated execution does not identify a generated transformation"
        )
    return (
        _input_path(suite.get("path"), "generated suite path", require_file=False),
        _input_path(transformation.get("path"), "transformation path"),
    )


def _verify_recorded_hashes(
    execution: dict[str, Any], suite_dir: Path, transformation_path: Path
) -> None:
    inputs = execution["inputs"]
    recorded_suite_hash = inputs["suite"].get("sha256")
    recorded_transformation_hash = inputs["transformation"].get("sha256")
    actual_suite_hash = directory_sha256(suite_dir)
    actual_transformation_hash = file_sha256(transformation_path)
    if recorded_suite_hash != actual_suite_hash:
        raise FailureReportError(
            "generated suite no longer matches its recorded sha256"
        )
    if recorded_transformation_hash != actual_transformation_hash:
        raise FailureReportError(
            "generated transformation no longer matches its recorded sha256"
        )


def _execution_stage_evidence(
    path: Path,
    generated_execution_path: Path,
    suite_dir: Path,
    transformation_path: Path,
    attempt: int,
    generated_execution: dict[str, Any],
) -> dict[str, Any]:
    """Pin the observation to the requested immutable execution attempt."""
    expected_suffix = (
        "stages",
        "execution",
        "attempts",
        f"attempt-{attempt:03d}",
        "evidence.json",
    )
    if path.parts[-len(expected_suffix) :] != expected_suffix:
        raise FailureReportError(
            "execution_evidence path does not match the requested execution attempt"
        )

    payload = _read_object(path, "execution stage evidence")
    pairs = payload.get("details", {}).get("pairs")
    if not isinstance(pairs, list):
        raise FailureReportError("execution stage evidence has no details.pairs array")
    matching = _matching_execution_pairs(pairs, generated_execution_path)
    if len(matching) != 1:
        raise FailureReportError(
            "execution attempt must reference the generated execution exactly once"
        )

    pair = matching[0]
    pair_suite = _input_path(pair.get("suite"), "pair suite", require_file=False)
    pair_transformation = _input_path(pair.get("transformation"), "pair transformation")
    if pair_suite != suite_dir or pair_transformation != transformation_path:
        raise FailureReportError(
            "execution pair inputs disagree with recorded observation"
        )
    assertions_passed = _observation(generated_execution, GENERATED_EXECUTION_LABEL)[
        "assertions_passed"
    ]
    if pair.get("assertions_passed") is not assertions_passed:
        raise FailureReportError(
            "execution pair assertion result disagrees with recorded observation"
        )
    return _json_artifact(path)


def _matching_execution_pairs(
    pairs: list[Any], generated_execution_path: Path
) -> list[dict[str, Any]]:
    """Find well-formed pairs that cite the requested execution observation."""
    matching: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        try:
            evidence_path = _input_path(pair.get("evidence"), "pair evidence")
        except FailureReportError:
            continue
        if evidence_path == generated_execution_path:
            matching.append(pair)
    return matching


def _observation(execution: dict[str, Any], label: str) -> dict[str, Any]:
    observation = execution.get("observation")
    if not isinstance(observation, dict):
        raise FailureReportError(f"{label} has no observation object")
    for field in ("assertions_evaluated", "assertions_passed"):
        if not isinstance(observation.get(field), bool):
            raise FailureReportError(f"{label} observation.{field} must be boolean")
    return observation


def _syntax_check(evidence: dict[str, Any], transformation: Path) -> dict[str, Any]:
    if isinstance(evidence.get("parsed"), bool):
        diagnostic = evidence.get("diagnostic", "")
        return {
            "status": "passed" if evidence["parsed"] else "failed",
            "parser_diagnostics": _diagnostic_list(diagnostic),
        }

    details = evidence.get("details")
    if not isinstance(details, dict):
        raise FailureReportError("syntax evidence has no details object")
    target = transformation.resolve()
    passed = _resolved_path_set(details.get("passed_transformations", []))
    failed = _resolved_path_set(details.get("failed_transformations", []))
    if target in passed and target in failed:
        raise FailureReportError(
            "transformation is both passed and failed in syntax evidence"
        )
    if target not in passed and target not in failed:
        raise FailureReportError("transformation is absent from syntax evidence")

    selected_diagnostics = _selected_syntax_diagnostics(
        details.get("diagnostics", {}), target, target in failed
    )
    return {
        "status": "passed" if target in passed else "failed",
        "parser_diagnostics": _diagnostic_list(selected_diagnostics),
    }


def _selected_syntax_diagnostics(
    diagnostics: object, target: Path, target_failed: bool
) -> object:
    if not isinstance(diagnostics, dict):
        return diagnostics if target_failed else []
    for raw_path, diagnostic in diagnostics.items():
        try:
            candidate = _input_path(raw_path, "diagnostic path")
        except FailureReportError:
            continue
        if candidate == target:
            return diagnostic
    return []


def _diagnostic_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(entry) for entry in value if str(entry).strip()]
    if isinstance(value, dict):
        return [f"{key}: {entry}" for key, entry in sorted(value.items())]
    return [str(value)]


def _semantic_status(observation: dict[str, Any]) -> str:
    if observation["assertions_evaluated"] is not True:
        return "execution_error"
    return "passed" if observation["assertions_passed"] else "failed"


def _reference_result(path: Path | None, identity: dict[str, Any]) -> dict[str, Any]:
    if path is None:
        return {"status": "not_run", "observation": None, "evidence": None}
    execution = _read_execution(path, identity, "reference execution")
    transformation = execution.get("inputs", {}).get("transformation", {})
    if transformation.get("role") != "reference_transformation":
        raise FailureReportError(
            "reference execution does not identify a reference transformation"
        )
    observation = _observation(execution, "reference execution")
    return {
        "status": "passed" if observation["assertions_passed"] else "failed",
        "observation": observation,
        "evidence": _json_artifact(path),
    }


def _task_description(
    identity: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    path = (
        TARGET.prompt_assets
        / "task_prompts"
        / str(identity["language"])
        / f"{identity['task_id']}.txt"
    )
    artifact = _text_artifact(_input_path(path, "task description"))
    recorded_hash = (
        manifest.get("provenance", {}).get("input_hashes", {}).get("task_prompt")
    )
    if recorded_hash is not None and artifact["sha256"] != recorded_hash:
        raise FailureReportError(
            "task description no longer matches manifest provenance"
        )
    return artifact


def _metamodel_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    recorded = manifest.get("provenance", {}).get("input_hashes", {}).get("metamodels")
    if not isinstance(recorded, dict) or not recorded:
        raise FailureReportError("manifest provenance contains no exact metamodels")
    artifacts: list[dict[str, Any]] = []
    for raw_path, expected_hash in sorted(recorded.items()):
        path = _input_path(raw_path, "metamodel path")
        artifact = _text_artifact(path)
        if artifact["sha256"] != expected_hash:
            raise FailureReportError(
                f"metamodel no longer matches manifest provenance: {raw_path}"
            )
        artifacts.append(artifact)
    return artifacts


def _resolved_path_set(value: object) -> set[Path]:
    if not isinstance(value, list):
        raise FailureReportError("syntax transformation list must be an array")
    resolved: set[Path] = set()
    for index, raw_path in enumerate(value):
        resolved.add(_input_path(raw_path, f"syntax transformation[{index}]").resolve())
    return resolved


@dataclass(frozen=True)
class RecordedExecution:
    """What one request resolves to before either report shape is chosen.

    Both report types start from the same six facts, in the same order, and a
    difference between them here would mean the two documents describe
    different executions. Resolving them once removes that possibility.
    """

    manifest: dict[str, Any]
    identity: dict[str, Any]
    generated_execution: dict[str, Any]
    suite_dir: Path
    transformation_path: Path
    stage_evidence: dict[str, Any]


@dataclass(frozen=True)
class ReportContext:
    """The verdicts and task context every report states about that execution."""

    syntax_check: dict[str, Any]
    observation: dict[str, Any]
    semantic_status: str
    reference_result: dict[str, Any]
    task_description: dict[str, Any]
    metamodels: list[dict[str, Any]]


def resolve_recorded_execution(request: Any) -> RecordedExecution:
    """Read the run, its recorded execution, and the inputs that produced it."""
    manifest = _read_object(request.run_manifest, "run manifest")
    identity = _identity(manifest, request.attempt)
    generated_execution = _read_execution(
        request.generated_execution, identity, GENERATED_EXECUTION_LABEL
    )
    suite_dir, transformation_path = _generated_inputs(generated_execution)
    _verify_recorded_hashes(generated_execution, suite_dir, transformation_path)
    stage_evidence = _execution_stage_evidence(
        request.execution_evidence,
        request.generated_execution,
        suite_dir,
        transformation_path,
        request.attempt,
        generated_execution,
    )
    return RecordedExecution(
        manifest=manifest,
        identity=identity,
        generated_execution=generated_execution,
        suite_dir=suite_dir,
        transformation_path=transformation_path,
        stage_evidence=stage_evidence,
    )


def resolve_report_context(request: Any, recorded: RecordedExecution) -> ReportContext:
    """Derive the parser verdict, the observation, and the task context.

    Called at the point each builder needs them rather than eagerly with
    :func:`resolve_recorded_execution`: the per-case builder selects its test
    case first, and reading the syntax evidence earlier would change which
    refusal a malformed request reports.
    """
    observation = _observation(recorded.generated_execution, GENERATED_EXECUTION_LABEL)
    return ReportContext(
        syntax_check=_syntax_check(
            _read_object(request.syntax_evidence, "syntax evidence"),
            recorded.transformation_path,
        ),
        observation=observation,
        semantic_status=_semantic_status(observation),
        reference_result=_reference_result(
            request.reference_execution, identity=recorded.identity
        ),
        task_description=_task_description(recorded.identity, recorded.manifest),
        metamodels=_metamodel_artifacts(recorded.manifest),
    )
