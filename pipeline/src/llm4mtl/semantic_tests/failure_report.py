"""Assemble one per-assertion semantic-test failure report.

The module only aggregates facts that earlier stages recorded.  It does not
compare models, classify the source of a failure, call an LLM, or choose a
workflow route.  In particular, ``actual_vs_expected`` must come from the
comparator or harness that observed the mismatch; this module refuses to invent
that evidence.

Run it through the experiment orchestrator with::

    llm4mtl diagnosis report \
      --request request.json --output artifacts/work/.../failure-report.json

The module also keeps a direct ``python -m llm4mtl.semantic_tests.failure_report``
entry point for narrow local use; both paths call the same assembler.

The request is one JSON object with these fields::

    {
      "run_manifest": "artifacts/work/runs/<run>/manifest.json",
      "syntax_evidence": ".../stages/syntax-validation/.../evidence.json",
      "execution_evidence": ".../stages/execution/attempts/attempt-001/evidence.json",
      "generated_execution": ".../suite_execution.json",
      "reference_execution": ".../suite_execution.json",  # optional
      "test_case_id": "case_name",
      "assertion_id": "assertion-001",
      "attempt": 1,
      "actual_target_models": [".../snapshot.xmi"],
      "surefire_reports": [".../TEST-GeneratedTest.xml"],   # optional, see below
      "execution_log": ".../execution.log",                 # optional
      "actual_vs_expected": {                                # required for diagnosis
        "missing_elements": [],
        "extra_elements": [],
        "wrong_types": [],
        "wrong_attributes": [],
        "reference_mismatches": []
      }
    }

``assertion_id`` is either an explicit assertion ``id`` from
``semantic_cases.json`` or the stable positional id ``assertion-NNN``.  Input
models, the generated transformation and suite, the reviewed task description,
and exact metamodels are resolved from the recorded identities.  Every input
path must stay inside the repository, and the output must stay under
``artifacts/work``.  The output is created once and never overwritten.

``surefire_reports`` and ``execution_log`` may be omitted, and normally should
be: the run archives its own Maven output and Surefire XML beside each execution
observation, and that archive is the only copy that still describes the
execution once the next pair's ``mvn clean`` has run.  Omitting them reads the
archive; naming them explicitly still works for evidence held elsewhere.  A
request that omits them for an execution with no archive is refused rather than
producing a report whose runtime evidence is silently empty.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from llm4mtl.paths import REPO_ROOT, TARGET
from llm4mtl.semantic_tests.codegen.java_rendering import sanitize_method_name
from llm4mtl.semantic_tests.execution_evidence import archived_execution_evidence
from llm4mtl.serialization.json_io import read_json, write_json_once
from llm4mtl.transformation_execution.hashing import directory_sha256, file_sha256

SCHEMA_VERSION = "1.0"
DIFF_FIELDS = (
    "missing_elements",
    "extra_elements",
    "wrong_types",
    "wrong_attributes",
    "reference_mismatches",
)
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class FailureReportError(ValueError):
    """Raised when recorded evidence cannot form a trustworthy report."""


@dataclass(frozen=True)
class ReportRequest:
    """Validated paths and selectors for one report assembly."""

    run_manifest: Path
    syntax_evidence: Path
    execution_evidence: Path
    generated_execution: Path
    reference_execution: Path | None
    test_case_id: str
    assertion_id: str
    attempt: int
    actual_target_models: tuple[Path, ...]
    surefire_reports: tuple[Path, ...]
    execution_log: Path | None
    actual_vs_expected: dict[str, list[Any]] | None

    @classmethod
    def from_payload(cls, payload: object) -> ReportRequest:
        """Validate the request boundary and resolve every supplied path."""
        if not isinstance(payload, dict):
            raise FailureReportError("request must be one JSON object")
        allowed_fields = {
            "run_manifest",
            "syntax_evidence",
            "execution_evidence",
            "generated_execution",
            "reference_execution",
            "test_case_id",
            "assertion_id",
            "attempt",
            "actual_target_models",
            "surefire_reports",
            "execution_log",
            "actual_vs_expected",
        }
        unknown_fields = sorted(set(payload) - allowed_fields)
        if unknown_fields:
            raise FailureReportError(
                f"request contains unknown fields: {', '.join(unknown_fields)}"
            )

        test_case_id = _required_string(payload, "test_case_id")
        assertion_id = _required_string(payload, "assertion_id")
        attempt = payload.get("attempt")
        if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
            raise FailureReportError("attempt must be a positive integer")

        actual_vs_expected = _validate_difference(payload.get("actual_vs_expected"))
        generated_execution = _input_path(
            payload.get("generated_execution"), "generated_execution"
        )
        # The workspace those reports were produced in is wiped by the next
        # `mvn clean`, so a request that named them there would break as soon as
        # the run continued. Omitting them therefore means "read the run's own
        # archive", which is the only copy that still describes this execution.
        #
        # Nothing is inferred either way: an archive that recorded no Surefire
        # report yields no report, and a request that names neither an explicit
        # path nor an archived execution is refused rather than producing a
        # report whose runtime evidence is silently empty.
        archived = archived_execution_evidence(generated_execution)
        if "surefire_reports" not in payload and archived.directory is None:
            raise FailureReportError(
                "surefire_reports must be an array of paths, or the generated "
                "execution must have archived execution evidence beside it"
            )
        return cls(
            run_manifest=_input_path(payload.get("run_manifest"), "run_manifest"),
            syntax_evidence=_input_path(payload.get("syntax_evidence"), "syntax_evidence"),
            execution_evidence=_input_path(
                payload.get("execution_evidence"), "execution_evidence"
            ),
            generated_execution=generated_execution,
            reference_execution=_optional_input_path(
                payload.get("reference_execution"), "reference_execution"
            ),
            test_case_id=test_case_id,
            assertion_id=assertion_id,
            attempt=attempt,
            actual_target_models=_input_paths(
                payload.get("actual_target_models"), "actual_target_models"
            ),
            surefire_reports=(
                _input_paths(payload["surefire_reports"], "surefire_reports")
                if "surefire_reports" in payload
                else archived.surefire_reports
            ),
            execution_log=(
                _optional_input_path(payload.get("execution_log"), "execution_log")
                if "execution_log" in payload
                else archived.execution_log
            ),
            actual_vs_expected=actual_vs_expected,
        )


def build_failure_report(request: ReportRequest) -> dict[str, Any]:
    """Build a self-contained report for one test case and assertion.

    Diagnosis eligibility is a fact derived only from the syntax observation
    and generated-transformation execution.  A bundle is emitted only when the
    parser passed and an evaluated semantic assertion failed.
    """
    manifest = _read_object(request.run_manifest, "run manifest")
    identity = _identity(manifest, request.attempt)
    generated_execution = _read_execution(
        request.generated_execution, identity, "generated execution"
    )
    suite_dir, transformation_path = _generated_inputs(generated_execution)
    _verify_recorded_hashes(generated_execution, suite_dir, transformation_path)
    execution_stage_evidence = _execution_stage_evidence(
        request.execution_evidence,
        request.generated_execution,
        suite_dir,
        transformation_path,
        request.attempt,
        generated_execution,
    )

    semantic_cases_path = suite_dir / "semantic_cases.json"
    semantic_cases = _read_object(semantic_cases_path, "semantic cases")
    test_case = _select_test_case(semantic_cases, request.test_case_id)
    assertion = _select_assertion(test_case, request.assertion_id)

    syntax_check = _syntax_check(
        _read_object(request.syntax_evidence, "syntax evidence"),
        transformation_path,
    )
    observation = _observation(generated_execution, "generated execution")
    semantic_status = _semantic_status(observation)
    is_diagnosis_eligible = (
        syntax_check["status"] == "passed"
        and observation["assertions_evaluated"] is True
        and observation["assertions_passed"] is False
    )

    task_description = _task_description(identity, manifest)
    metamodels = _metamodel_artifacts(manifest)
    input_models = _input_models(test_case, suite_dir)
    expected_target_models = _expected_target_models(test_case, suite_dir)

    actual_target_models = [
        _text_artifact(path) for path in request.actual_target_models
    ]
    surefire_evidence = _surefire_evidence(
        request.surefire_reports, request.test_case_id
    )
    execution_error = {
        "error_summary": str(observation.get("error_summary", "")),
        "exceptions": surefire_evidence["exceptions"],
        "stack_traces": surefire_evidence["stack_traces"],
        "execution_log": (
            _text_artifact(request.execution_log)
            if request.execution_log is not None
            else None
        ),
        "surefire": surefire_evidence["test_cases"],
    }

    reference_result = _reference_result(request.reference_execution, identity)
    versions = {
        "generated_transformation": {
            "sha256": file_sha256(transformation_path),
            "path": _repository_path(transformation_path),
        },
        "generated_test": {
            "sha256": directory_sha256(suite_dir),
            "path": _repository_path(suite_dir),
            "renderer_version": manifest.get("provenance", {}).get(
                "renderer_version"
            ),
        },
    }

    difference = (
        {"available": True, **request.actual_vs_expected}
        if request.actual_vs_expected is not None
        else {"available": False, **{field: None for field in DIFF_FIELDS}}
    )
    if is_diagnosis_eligible:
        _require_concrete_assertion_failure(test_case, assertion, surefire_evidence)
        _require_diagnosis_evidence(
            input_models=input_models,
            actual_target_models=actual_target_models,
            difference=request.actual_vs_expected,
        )

    test_case_result = {
        "test_case_id": request.test_case_id,
        "assertion_id": request.assertion_id,
        "semantic_status": semantic_status,
        "syntax_check": syntax_check,
        "test_case": test_case,
        "assertion": assertion,
        "input_model": {
            "models": input_models,
            "changes": test_case.get("changes", []),
        },
        "expected_output_or_properties": {
            "assertion": assertion,
            "target_models": expected_target_models,
        },
        "actual_target_model": actual_target_models,
        "actual_vs_expected": difference,
        "execution": {
            "observation": observation,
            "stage_evidence": execution_stage_evidence,
            "error": execution_error,
        },
        "reference_transformation_result": reference_result,
        "versions": versions,
    }

    evidence_bundle = None
    if is_diagnosis_eligible:
        evidence_bundle = {
            "original_task_description": task_description,
            "relevant_source_and_target_metamodel_constraints": metamodels,
            "generated_transformation": _text_artifact(transformation_path),
            "failing_test_case_or_assertion": {
                "test_case_id": request.test_case_id,
                "assertion_id": request.assertion_id,
                "test_case": test_case,
                "assertion": assertion,
            },
            "input_model": test_case_result["input_model"],
            "expected_output_or_properties": test_case_result[
                "expected_output_or_properties"
            ],
            "actual_target_model": actual_target_models,
            "structured_actual_vs_expected_difference": difference,
            "execution_error_or_log": execution_error,
            "reference_transformation_result": reference_result,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": "semantic_test_case_failure",
        "identity": identity,
        "task_context": {
            "original_description": task_description,
            "metamodel_constraints": metamodels,
        },
        "test_case_result": test_case_result,
        "source_diagnosis": {
            "eligible": is_diagnosis_eligible,
            "reason": _diagnosis_reason(syntax_check, observation),
            "evidence_bundle": evidence_bundle,
            "allowed_classifications": [
                "transformation_defect",
                "test_defect",
                "ambiguous",
            ],
            "required_result_fields": [
                "classification",
                "confidence",
                "reasoning_summary",
                "evidence",
                "test_case_id",
            ],
        },
    }


def write_failure_report(request: ReportRequest, output: Path) -> dict[str, Any]:
    """Create one immutable report under ``artifacts/work`` and return it."""
    resolved_output = _output_path(output)
    report = build_failure_report(request)
    try:
        write_json_once(resolved_output, report)
    except FileExistsError as exc:
        raise FailureReportError(
            f"report already exists and is immutable: {_repository_path(resolved_output)}"
        ) from exc
    return report


def load_report_request(path: Path) -> ReportRequest:
    """Read and validate one repository-contained failure-report request."""
    request_path = _input_path(path, "request")
    try:
        payload = read_json(request_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(
            f"cannot read failure-report request from {request_path}: {exc}"
        ) from exc
    return ReportRequest.from_payload(payload)


def _identity(manifest: dict[str, Any], attempt: int) -> dict[str, Any]:
    required = (
        "run_id",
        "task",
        "language",
        "transformation_model",
        "test_generation_model",
    )
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
        "model": manifest["transformation_model"],
        "attempt": attempt,
        "transformation_model": manifest["transformation_model"],
        "test_generation_model": manifest["test_generation_model"],
        "transformation_strategy": manifest.get("transformation_strategy"),
        "test_generation_strategy": manifest.get("test_generation_strategy"),
    }


def _read_execution(
    path: Path, identity: dict[str, Any], label: str
) -> dict[str, Any]:
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
        raise FailureReportError("generated execution does not identify a generated suite")
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
        raise FailureReportError("generated suite no longer matches its recorded sha256")
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
    expected_attempt_dir = f"attempt-{attempt:03d}"
    if (
        path.name != "evidence.json"
        or path.parent.name != expected_attempt_dir
        or path.parent.parent.name != "attempts"
        or path.parent.parent.parent.name != "execution"
        or path.parent.parent.parent.parent.name != "stages"
    ):
        raise FailureReportError(
            "execution_evidence path does not match the requested execution attempt"
        )

    payload = _read_object(path, "execution stage evidence")
    pairs = payload.get("details", {}).get("pairs")
    if not isinstance(pairs, list):
        raise FailureReportError("execution stage evidence has no details.pairs array")
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
    if len(matching) != 1:
        raise FailureReportError(
            "execution attempt must reference the generated execution exactly once"
        )

    pair = matching[0]
    pair_suite = _input_path(pair.get("suite"), "pair suite", require_file=False)
    pair_transformation = _input_path(pair.get("transformation"), "pair transformation")
    if pair_suite != suite_dir or pair_transformation != transformation_path:
        raise FailureReportError("execution pair inputs disagree with recorded observation")
    assertions_passed = _observation(
        generated_execution, "generated execution"
    )["assertions_passed"]
    if pair.get("assertions_passed") is not assertions_passed:
        raise FailureReportError(
            "execution pair assertion result disagrees with recorded observation"
        )
    return _json_artifact(path)


def _observation(execution: dict[str, Any], label: str) -> dict[str, Any]:
    observation = execution.get("observation")
    if not isinstance(observation, dict):
        raise FailureReportError(f"{label} has no observation object")
    for field in ("assertions_evaluated", "assertions_passed"):
        if not isinstance(observation.get(field), bool):
            raise FailureReportError(f"{label} observation.{field} must be boolean")
    return observation


def _select_test_case(
    semantic_cases: dict[str, Any], test_case_id: str
) -> dict[str, Any]:
    tests = semantic_cases.get("tests")
    if not isinstance(tests, list):
        raise FailureReportError("semantic_cases.json has no tests array")
    matching = [
        test
        for test in tests
        if isinstance(test, dict)
        and str(test.get("id") or test.get("name") or "") == test_case_id
    ]
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one test case {test_case_id!r}, found {len(matching)}"
        )
    return matching[0]


def _select_assertion(test_case: dict[str, Any], assertion_id: str) -> dict[str, Any]:
    assertions = test_case.get("assertions")
    if not isinstance(assertions, list):
        raise FailureReportError("selected test case has no assertions array")
    matching: list[dict[str, Any]] = []
    for index, assertion in enumerate(assertions, start=1):
        if not isinstance(assertion, dict):
            continue
        recorded_id = str(assertion.get("id") or f"assertion-{index:03d}")
        if recorded_id == assertion_id:
            matching.append({"id": recorded_id, **assertion})
    if len(matching) != 1:
        raise FailureReportError(
            f"expected exactly one assertion {assertion_id!r}, found {len(matching)}"
        )
    return matching[0]


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
        raise FailureReportError("transformation is both passed and failed in syntax evidence")
    if target not in passed and target not in failed:
        raise FailureReportError("transformation is absent from syntax evidence")

    diagnostics = details.get("diagnostics", {})
    selected_diagnostics: object = []
    if isinstance(diagnostics, dict):
        for raw_path, diagnostic in diagnostics.items():
            try:
                candidate = _input_path(raw_path, "diagnostic path")
            except FailureReportError:
                continue
            if candidate == target:
                selected_diagnostics = diagnostic
                break
    elif target in failed:
        selected_diagnostics = diagnostics
    return {
        "status": "passed" if target in passed else "failed",
        "parser_diagnostics": _diagnostic_list(selected_diagnostics),
    }


def _semantic_status(observation: dict[str, Any]) -> str:
    if observation["assertions_evaluated"] is not True:
        return "execution_error"
    return "passed" if observation["assertions_passed"] else "failed"


def _reference_result(
    path: Path | None, identity: dict[str, Any]
) -> dict[str, Any]:
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
        manifest.get("provenance", {})
        .get("input_hashes", {})
        .get("task_prompt")
    )
    if recorded_hash is not None and artifact["sha256"] != recorded_hash:
        raise FailureReportError("task description no longer matches manifest provenance")
    return artifact


def _metamodel_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    recorded = (
        manifest.get("provenance", {})
        .get("input_hashes", {})
        .get("metamodels")
    )
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


def _input_models(test_case: dict[str, Any], suite_dir: Path) -> list[dict[str, Any]]:
    models = test_case.get("models", [])
    if not isinstance(models, list):
        raise FailureReportError("test case models must be an array")
    artifacts: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict) or model.get("role") not in {"source", "inout"}:
            continue
        raw_path = model.get("path")
        if raw_path is None:
            continue
        artifacts.append(
            {
                "model": model,
                "artifact": _text_artifact(
                    _suite_artifact_path(suite_dir, raw_path, "input model")
                ),
            }
        )
    return artifacts


def _expected_target_models(
    test_case: dict[str, Any], suite_dir: Path
) -> list[dict[str, Any]]:
    models = test_case.get("models", [])
    if not isinstance(models, list):
        return []
    artifacts: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict) or model.get("role") != "target":
            continue
        raw_path = model.get("path")
        if raw_path is None or model.get("generated") is True:
            continue
        artifacts.append(
            {
                "model": model,
                "artifact": _text_artifact(
                    _suite_artifact_path(suite_dir, raw_path, "expected target model")
                ),
            }
        )
    return artifacts


def _surefire_evidence(
    report_paths: Sequence[Path], test_case_id: str
) -> dict[str, Any]:
    method_name = sanitize_method_name(test_case_id)
    test_cases: list[dict[str, Any]] = []
    exceptions: list[dict[str, str]] = []
    stack_traces: list[str] = []
    for path in report_paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError) as exc:
            raise FailureReportError(f"invalid Surefire report {path}: {exc}") from exc
        for case in root.iter("testcase"):
            if case.get("name") != method_name:
                continue
            failure = case.find("failure")
            error = case.find("error")
            node = error if error is not None else failure
            status = (
                "error"
                if error is not None
                else "failed"
                if failure is not None
                else "passed"
            )
            test_cases.append(
                {
                    "report": _repository_path(path),
                    "test_class": case.get("classname"),
                    "test_method": case.get("name"),
                    "duration_seconds": case.get("time"),
                    "status": status,
                }
            )
            if node is not None:
                exception = {
                    "type": str(node.get("type") or node.tag),
                    "message": str(node.get("message") or ""),
                }
                exceptions.append(exception)
                trace = (node.text or "").strip()
                if trace:
                    stack_traces.append(trace)
    return {
        "test_cases": test_cases,
        "exceptions": exceptions,
        "stack_traces": stack_traces,
    }


def _require_diagnosis_evidence(
    *,
    input_models: list[dict[str, Any]],
    actual_target_models: list[dict[str, Any]],
    difference: dict[str, list[Any]] | None,
) -> None:
    if not input_models:
        raise FailureReportError(
            "diagnosis-eligible failure has no recorded input model artifact"
        )
    if not actual_target_models:
        raise FailureReportError(
            "diagnosis-eligible failure has no recorded actual target model"
        )
    if difference is None:
        raise FailureReportError(
            "diagnosis-eligible failure requires structured actual_vs_expected"
        )


def _require_concrete_assertion_failure(
    test_case: dict[str, Any],
    assertion: dict[str, Any],
    surefire_evidence: dict[str, Any],
) -> None:
    """Prove that the selected case and assertion are the recorded failure."""
    failed_cases = [
        case
        for case in surefire_evidence["test_cases"]
        if case.get("status") == "failed"
    ]
    if len(failed_cases) != 1:
        raise FailureReportError(
            "diagnosis-eligible report requires exactly one matching Surefire "
            f"assertion failure, found {len(failed_cases)}"
        )

    selected_message = _assertion_message(assertion)
    assertion_messages = [
        _assertion_message(candidate)
        for candidate in test_case.get("assertions", [])
        if isinstance(candidate, dict)
    ]
    if assertion_messages.count(selected_message) != 1:
        raise FailureReportError(
            "selected assertion message is not unique within the test case"
        )
    recorded_failure = "\n".join(
        [
            *(str(exception.get("message", "")) for exception in surefire_evidence["exceptions"]),
            *(str(trace) for trace in surefire_evidence["stack_traces"]),
        ]
    )
    if selected_message not in recorded_failure:
        raise FailureReportError(
            "selected assertion_id does not match the Surefire failure message"
        )


def _assertion_message(assertion: dict[str, Any]) -> str:
    explicit = assertion.get("message")
    if isinstance(explicit, str) and explicit:
        return explicit
    required = ("kind", "model", "type")
    if not all(field in assertion for field in required):
        raise FailureReportError(
            "assertion needs an explicit message or kind/model/type identity"
        )
    return (
        f"{assertion['kind']} assertion for "
        f"{assertion['model']}::{assertion['type']}"
    )


def _diagnosis_reason(
    syntax_check: dict[str, Any], observation: dict[str, Any]
) -> str:
    if syntax_check["status"] != "passed":
        return "transformation_parser_check_failed"
    if observation["assertions_evaluated"] is not True:
        return "semantic_assertions_not_evaluated"
    if observation["assertions_passed"] is True:
        return "semantic_test_passed"
    return "parser_passed_and_semantic_test_failed"


def _validate_difference(value: object) -> dict[str, list[Any]] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FailureReportError("actual_vs_expected must be an object or null")
    missing = [field for field in DIFF_FIELDS if field not in value]
    unknown = sorted(set(value) - set(DIFF_FIELDS))
    if missing or unknown:
        problems = []
        if missing:
            problems.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            problems.append(f"unknown fields: {', '.join(unknown)}")
        raise FailureReportError(f"invalid actual_vs_expected: {'; '.join(problems)}")
    normalized: dict[str, list[Any]] = {}
    for field in DIFF_FIELDS:
        entries = value[field]
        if not isinstance(entries, list):
            raise FailureReportError(f"actual_vs_expected.{field} must be an array")
        normalized[field] = entries
    return normalized


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise FailureReportError(f"cannot read {label} from {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FailureReportError(f"{label} must contain one JSON object")
    return payload


def _text_artifact(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FailureReportError(f"cannot read UTF-8 evidence file {path}: {exc}") from exc
    return {
        "path": _repository_path(path),
        "sha256": file_sha256(path),
        "content": content,
    }


def _json_artifact(path: Path) -> dict[str, Any]:
    artifact = _text_artifact(path)
    try:
        artifact["document"] = json.loads(artifact["content"])
    except json.JSONDecodeError as exc:
        raise FailureReportError(f"invalid JSON evidence file {path}: {exc}") from exc
    return artifact


def _suite_artifact_path(suite_dir: Path, raw_path: object, label: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise FailureReportError(f"{label} path must be a non-empty string")
    candidate = (suite_dir / raw_path).resolve()
    try:
        candidate.relative_to(suite_dir.resolve())
    except ValueError as exc:
        raise FailureReportError(f"{label} escapes the generated suite: {raw_path}") from exc
    if not candidate.is_file():
        raise FailureReportError(f"{label} does not exist: {raw_path}")
    return candidate


def _input_path(
    value: object, label: str, *, require_file: bool = True
) -> Path:
    if isinstance(value, Path):
        candidate = value
    elif isinstance(value, str) and value:
        candidate = Path(value)
    else:
        raise FailureReportError(f"{label} must be a non-empty path string")
    resolved = (
        candidate.resolve()
        if candidate.is_absolute()
        else (REPO_ROOT / candidate).resolve()
    )
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise FailureReportError(f"{label} escapes the repository: {candidate}") from exc
    if require_file and not resolved.is_file():
        raise FailureReportError(f"{label} is not a file: {candidate}")
    if not require_file and not resolved.is_dir():
        raise FailureReportError(f"{label} is not a directory: {candidate}")
    return resolved


def _optional_input_path(value: object, label: str) -> Path | None:
    return None if value is None else _input_path(value, label)


def _input_paths(value: object, label: str) -> tuple[Path, ...]:
    if not isinstance(value, list):
        raise FailureReportError(f"{label} must be an array of paths")
    return tuple(_input_path(path, f"{label}[{index}]") for index, path in enumerate(value))


def _output_path(value: Path) -> Path:
    candidate = value if value.is_absolute() else REPO_ROOT / value
    resolved = candidate.resolve()
    try:
        resolved.relative_to(TARGET.artifacts_work.resolve())
    except ValueError as exc:
        raise FailureReportError("output must stay under artifacts/work") from exc
    return resolved


def _repository_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise FailureReportError(f"path escapes the repository: {path}") from exc


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise FailureReportError(f"{field} must be a non-empty string")
    return value


def _resolved_path_set(value: object) -> set[Path]:
    if not isinstance(value, list):
        raise FailureReportError("syntax transformation list must be an array")
    resolved: set[Path] = set()
    for index, raw_path in enumerate(value):
        resolved.add(_input_path(raw_path, f"syntax transformation[{index}]").resolve())
    return resolved


def _diagnostic_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(entry) for entry in value if str(entry).strip()]
    if isinstance(value, dict):
        return [f"{key}: {entry}" for key, entry in sorted(value.items())]
    return [str(value)]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble one immutable per-assertion semantic failure report."
    )
    parser.add_argument("--request", type=Path, required=True, help="JSON request file")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new report path below artifacts/work",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns non-zero without writing a partial report."""
    args = _parse_args(argv)
    try:
        request = load_report_request(args.request)
        write_failure_report(request, args.output)
    except (FailureReportError, FileExistsError, json.JSONDecodeError, OSError) as exc:
        print(f"failure report error: {exc}", file=sys.stderr)
        return 2
    print(_repository_path(_output_path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
