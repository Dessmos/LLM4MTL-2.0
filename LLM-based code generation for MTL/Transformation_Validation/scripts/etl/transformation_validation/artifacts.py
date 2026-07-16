"""Archive reproducible pass/fail bundles."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from transformation_validation.models import TransformationValidationResult
from transformation_validation.paths import relative_or_absolute


def archive_result(result: TransformationValidationResult, artifacts_root: Path) -> TransformationValidationResult:
    pair = result.pair
    bundle_dir = (
        artifacts_root.resolve()
        / pair.suite.task
        / result.status
        / pair.transformation.llm
        / pair.transformation.strategy
        / pair.suite.llm
        / pair.suite.strategy
        / pair.suite.suite_id
        / result.run_id
    )
    bundle_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(pair.transformation.path, bundle_dir / "transformation.etl")
    shutil.copytree(pair.suite.path, bundle_dir / "suite")

    archived = result.with_artifact_dir(relative_or_absolute(bundle_dir))
    manifest = {
        "run_id": result.run_id,
        "language": "ETL",
        "task": pair.suite.task,
        "status": result.status,
        "inputs": {
            "transformation": {
                "model": pair.transformation.llm,
                "strategy": pair.transformation.strategy,
                "source_path": relative_or_absolute(pair.transformation.path),
                "sha256": result.transformation_sha256,
                "archived_path": "transformation.etl",
            },
            "validated_suite": {
                "model": pair.suite.llm,
                "strategy": pair.suite.strategy,
                "suite_id": pair.suite.suite_id,
                "source_path": relative_or_absolute(pair.suite.path),
                "sha256": result.suite_sha256,
                "archived_path": "suite",
            },
        },
    }
    write_json(bundle_dir / "manifest.json", manifest)
    write_json(bundle_dir / "result.json", archived.as_row())
    (bundle_dir / "maven-output.log").write_text(result.maven_output + "\n", encoding="utf-8")
    if result.status == "failed":
        (bundle_dir / "repair_request.md").write_text(repair_request(archived), encoding="utf-8")
    return archived


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def repair_request(result: TransformationValidationResult) -> str:
    pair = result.pair
    return (
        "# Generated ETL transformation failure\n\n"
        f"Task: `{pair.suite.task}`\n\n"
        f"Failure stage: `{result.failure_stage}`\n\n"
        f"Error summary: `{result.error_summary}`\n\n"
        "Inspect `transformation.etl`, the complete reference-validated test oracle in "
        "`suite/`, and `maven-output.log`. Determine whether the generated transformation "
        "violates the intended semantics or fails to parse/execute, then return a corrected "
        "ETL transformation without weakening the tests.\n"
    )
