from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_ROOT = REPOSITORY_ROOT / "workflows" / "n8n"


def _workflow_documents() -> list[tuple[Path, dict[str, Any]]]:
    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(WORKFLOWS_ROOT.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("nodes"), list):
            documents.append((path, document))
    return documents


def _connected_models(document: dict[str, Any]) -> list[str]:
    nodes_by_name = {node["name"]: node for node in document["nodes"]}
    models: list[str] = []
    for source_name, connections in document.get("connections", {}).items():
        for output in connections.get("ai_languageModel", []):
            if not output:
                continue
            node = nodes_by_name[source_name]
            parameters = node.get("parameters", {})
            model = parameters.get("model", {}).get("value") or parameters.get("modelName")
            if model:
                models.append(_model_path_alias(model))
    for node in document["nodes"]:
        if node["type"] != "n8n-nodes-base.httpRequest":
            continue
        if "qwen2.5-coder:7b" in json.dumps(node.get("parameters", {})):
            models.append("qwen2-5-coder-7b")
    return models


def _model_path_alias(model: str) -> str:
    if "claude-sonnet-4" in model:
        return "claude-sonnet-4"
    if "gemini-2.5-pro" in model or "gemini-2-5-pro" in model:
        return "gemini-2-5-pro"
    return model


_NODE_REFERENCE = re.compile(r"\$\('([^']+)'\)")


def _writes_inside_artifacts(document: dict[str, Any], file_name: str) -> bool:
    """Whether a write node's target is contained in the artifacts mount.

    A file name is either the literal path or an expression reading a path some
    earlier node built. Following that reference keeps the containment check
    real for both: a node that derives its paths once still has to derive them
    under ``/data/artifacts``.
    """
    if file_name.startswith("=/data/artifacts/"):
        return True
    referenced = _NODE_REFERENCE.search(file_name)
    if referenced is None:
        return False
    source = next(
        (node for node in document["nodes"] if node["name"] == referenced.group(1)),
        None,
    )
    if source is None:
        return False
    return "/data/artifacts/" in json.dumps(source.get("parameters", {}))


class N8nArtifactRoutingTests(unittest.TestCase):
    def test_generated_file_writes_target_artifacts(self) -> None:
        write_count = 0
        for path, document in _workflow_documents():
            for node in document["nodes"]:
                parameters = node.get("parameters", {})
                if (
                    node["type"] == "n8n-nodes-base.readWriteFile"
                    and parameters.get("operation") == "write"
                ):
                    write_count += 1
                    self.assertTrue(
                        _writes_inside_artifacts(
                            document, parameters.get("fileName", "")
                        ),
                        f"{path}: {node['name']} writes outside artifacts",
                    )
                if node["type"] == "n8n-nodes-base.executeCommand":
                    command = parameters.get("command", "")
                    self.assertNotIn("snippets/responses", command, str(path))
                    self.assertNotIn("snippets/out", command, str(path))
        self.assertGreater(write_count, 0)

    def test_write_paths_identify_the_connected_model(self) -> None:
        for path, document in _workflow_documents():
            writes = [
                node["parameters"]["fileName"]
                for node in document["nodes"]
                if node["type"] == "n8n-nodes-base.readWriteFile"
                and node.get("parameters", {}).get("operation") == "write"
            ]
            if len(writes) != 1:
                continue
            models = _connected_models(document)
            if len(models) == 1:
                self.assertIn(models[0], writes[0], str(path))
            elif len(models) > 1:
                self.assertIn("llmName", writes[0], str(path))

    def test_diagnosis_is_persisted_with_provenance(self) -> None:
        path = WORKFLOWS_ROOT / "subworkflows" / "diagnosis" / "llm-diagnosis.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in document["nodes"]}

        validation_code = nodes["Validate Evidence Bundle"]["parameters"]["jsCode"]
        for evidence_field in (
            "original_task_description",
            "relevant_source_and_target_metamodel_constraints",
            "generated_transformation",
            "failing_test_case_or_assertion",
            "input_model",
            "expected_output_or_properties",
            "actual_target_model",
            "structured_actual_vs_expected_difference",
            "generated_execution_summary",
            "reference_transformation_result",
        ):
            self.assertIn(evidence_field, validation_code)
        # Both prepared report types must be readable: a case-level failure and
        # the pair-level failure that happened before any test method ran. Each
        # states its own eligibility reason and its own semantic status.
        for scope_marker in (
            "semantic_test_case_failure",
            "semantic_execution_pair_failure",
            "parser_passed_and_semantic_test_failed",
            "parser_passed_and_execution_failed_before_any_test",
            "execution_pair",
        ):
            self.assertIn(scope_marker, validation_code)
        # The bundle Python writes is the contract, and it carries more than a
        # diagnosis reads. Requiring an exact key set made every extra field a
        # hard failure, so presence is what is checked now.
        self.assertNotIn("must contain exactly", validation_code)
        self.assertIn("!(field in bundle)", validation_code)
        # `in`, not truthiness: an assertion failure carries stack_traces: [].
        self.assertNotIn("!bundle[field]", validation_code)
        self.assertNotIn("execution_error_or_log", validation_code)
        # The difference object stays mandatory, but an unavailable one is a
        # legitimate shape: no comparator produces the model-level diff yet, so
        # requiring it would reject every real report. A diff that claims to be
        # available must still be complete.
        self.assertIn("structured_actual_vs_expected_difference", validation_code)
        self.assertIn("typeof difference.available !== 'boolean'", validation_code)
        self.assertIn("difference.available === true &&", validation_code)
        self.assertNotIn("difference.available !== true", validation_code)

        # Every artifact path is derived once and read back by name. Rebuilding
        # one from $json after a Convert to File node resolves it to undefined.
        build_node = "Build Diagnosis Request Artifact"
        build_code = nodes[build_node]["parameters"]["jsCode"]
        for derived in ("artifact_directory", "request_path", "raw_response_path", "result_path"):
            self.assertIn(f"{derived}:", build_code)

        # The directory the workflow writes into is the one the stage service
        # prepares, so the two must name it identically. Below it the n8n
        # execution id names files, never a further directory the write node
        # would have to create.
        from llm4mtl.semantic_tests.diagnosis_preparation import diagnosis_response_dir

        prepared = diagnosis_response_dir(Path("/run"), 1).as_posix()
        self.assertTrue(prepared.endswith("responses/source-diagnosis/execution-attempt-001"))
        self.assertIn(
            "/responses/source-diagnosis/execution-attempt-${executionAttempt}`",
            build_code,
        )
        self.assertIn("const artifactPrefix = `${artifactDirectory}/n8n-execution-", build_code)
        for derived, suffix in (
            ("request_path", "__diagnosis_request.json"),
            ("raw_response_path", "__diagnosis_raw_response.txt"),
            ("result_path", "__diagnosis_result.json"),
        ):
            self.assertIn(f"{derived}: `${{artifactPrefix}}{suffix}`", build_code)
        self.assertNotIn("n8n-execution-${executionId}`;", build_code.split("artifactPrefix")[0])
        # Python prepares the per-attempt parent directory before this workflow
        # is exposed. Execute Command is unavailable in a default n8n container,
        # where it imports as an unrecognized node and takes its neighbours'
        # connections down with it.
        self.assertNotIn(
            "n8n-nodes-base.executeCommand",
            {node["type"] for node in document["nodes"]},
        )
        self.assertEqual(
            "Convert Diagnosis Request to File",
            document["connections"][build_node]["main"][0][0]["node"],
        )
        for writer, derived in (
            ("Write Diagnosis Request", "request_path"),
            ("Write Raw Diagnosis Response", "raw_response_path"),
            ("Write Diagnosis Result", "result_path"),
        ):
            written = nodes[writer]["parameters"]["fileName"]
            self.assertEqual(
                f"={{{{ $('{build_node}').first().json.{derived} }}}}", written
            )
            self.assertNotIn("$json.", written)

        provenance_code = nodes["Attach Diagnosis Provenance"]["parameters"]["jsCode"]
        self.assertIn("provider: context.provider", provenance_code)
        self.assertIn("model", provenance_code)
        self.assertIn("assertion_id", provenance_code)
        self.assertIn("parsed.assertion_id !== context.assertion_id", provenance_code)
        self.assertIn("transformation_defect", provenance_code)
        self.assertIn("test_defect", provenance_code)
        self.assertIn("ambiguous", provenance_code)
        self.assertNotIn("source.content", provenance_code)

        self.assertIn("diagnosis_request.json", build_code)
        self.assertIn("diagnosis_raw_response.txt", build_code)
        self.assertIn("diagnosis_result.json", build_code)

        request_code = build_code
        self.assertIn("/responses/source-diagnosis/", request_code)
        self.assertIn("messages", request_code)
        self.assertIn("system_prompt", request_code)
        self.assertIn("user_prompt", request_code)
        self.assertIn("assertion_id", request_code)
        self.assertIn("n8n-execution-", request_code)

        connections = document["connections"]
        self.assertEqual(
            "Call Diagnosis LLM",
            connections["Write Diagnosis Request"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Attach Diagnosis Provenance",
            connections["Write Raw Diagnosis Response"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Persist Diagnosis Artifact",
            connections["Write Diagnosis Result"]["main"][0][0]["node"],
        )

        return_code = nodes["Return Verdict"]["parameters"]["jsCode"]
        self.assertIn("assertion_id: verdict.assertion_id", return_code)

        master_path = WORKFLOWS_ROOT / "main" / "llm4mtl-agent-workflow.json"
        master = json.loads(master_path.read_text(encoding="utf-8"))
        master_nodes = {node["name"]: node for node in master["nodes"]}
        state_machine = master_nodes["State Machine"]["parameters"]["jsCode"]
        self.assertIn("assertion_id: verdict.assertion_id || null", state_machine)

        prompt_path = (
            REPOSITORY_ROOT
            / "prompt_assets"
            / "diagnosis"
            / "semantic_failure_diagnosis.md"
        )
        self.assertIn("assertion_id", prompt_path.read_text(encoding="utf-8"))

        persist = nodes["Persist Diagnosis Artifact"]
        self.assertEqual("n8n-nodes-base.httpRequest", persist["type"])
        self.assertIn("/runs/{{", persist["parameters"]["url"])
        self.assertIn("/diagnoses", persist["parameters"]["url"])

    def test_a_case_level_throw_is_readable_by_the_diagnosis(self) -> None:
        """The per-case scope covers both shapes of a per-case failure.

        Python attributes a Surefire ``<error>`` to the test method it names, so
        the report is per-case - but no assertion was evaluated, which makes the
        semantic status ``execution_error`` and the assertion null. Pinning both
        here keeps the guard from narrowing back to a lost assertion and turning
        every runtime failure into a workflow error.
        """
        path = WORKFLOWS_ROOT / "subworkflows" / "diagnosis" / "llm-diagnosis.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in document["nodes"]}
        validation_code = nodes["Validate Evidence Bundle"]["parameters"]["jsCode"]

        self.assertIn("semanticStatuses: ['failed', 'execution_error']", validation_code)
        self.assertIn("spec.semanticStatuses.includes(result.semantic_status)", validation_code)
        # A single expected status is what refused the runtime failures.
        self.assertNotIn("semanticStatus:", validation_code)
        # The case is required; the assertion is allowed to be null.
        self.assertIn("failing.assertion_id !== null &&", validation_code)
        self.assertNotIn("must identify one test case and assertion", validation_code)
        # A pair-level report still names neither.
        self.assertIn(
            "An execution-pair evidence bundle must name no test case and no assertion",
            validation_code,
        )

        prompt = (
            REPOSITORY_ROOT
            / "prompt_assets"
            / "diagnosis"
            / "semantic_failure_diagnosis.md"
        ).read_text(encoding="utf-8")
        # The verdict check compares the returned ids with the requested ones,
        # so the prompt has to say that null is the answer for a throw.
        self.assertIn("threw before any assertion was evaluated", prompt)
        self.assertIn("return `null` for\n`assertion_id`", prompt)

    def test_the_master_records_where_each_run_ended(self) -> None:
        """The terminal state reaches disk instead of only the n8n execution.

        Without it, reading a finished run means reconstructing its ending from
        the event log, from which artifacts are absent, and from the routing
        rules themselves — acceptable while debugging one run, and not as the
        input to a metrics module over hundreds.
        """
        master_path = WORKFLOWS_ROOT / "main" / "llm4mtl-agent-workflow.json"
        master = json.loads(master_path.read_text(encoding="utf-8"))
        nodes = {node["name"]: node for node in master["nodes"]}
        connections = master["connections"]

        record = nodes["Record Terminal Result"]
        self.assertEqual("n8n-nodes-base.httpRequest", record["type"])
        self.assertEqual("POST", record["parameters"]["method"])
        self.assertIn("/result", record["parameters"]["url"])
        body = record["parameters"]["jsonBody"]
        # Only what the orchestration owns; stage statuses are read off the run.
        for reported in (
            "status:",
            "terminal_state:",
            "run_mode:",
            "refinement_iterations_used:",
            "refinement_iterations_allowed:",
        ):
            self.assertIn(reported, body)
        self.assertNotIn("syntax_status", body)
        self.assertNotIn("semantic_status", body)

        # Each stage call states which refinement iteration it belongs to, so
        # the run's copy of the transformation is filed under the right one even
        # when the suite id deliberately stays behind.
        stage_body = nodes["Run Existing Python Stage"]["parameters"]["jsonBody"]
        self.assertIn(
            "refinement_iteration: $json.stage_iteration", stage_body
        )

        # The final branch records the ending before it reads the artifacts.
        final_branch = connections["Route Next Action"]["main"][4]
        self.assertEqual("Record Terminal Result", final_branch[0]["node"])
        self.assertEqual(
            "Read Final Run Artifacts",
            connections["Record Terminal Result"]["main"][0][0]["node"],
        )
        # That node no longer receives the state directly, so it may not read
        # the run id from $json.
        artifacts_url = nodes["Read Final Run Artifacts"]["parameters"]["url"]
        self.assertIn("$('State Machine').first().json.current.run_id", artifacts_url)

    def test_no_workflow_tree_keeps_its_own_copy_of_the_benchmark(self) -> None:
        """Task inputs live in benchmark/ only.

        Each n8n tree used to carry an ``mtl_snippets/`` copy of the reference
        transformations, mounted at ``/data/snippets``. Two copies of the same
        protected input is one copy too many: they drift, and a workflow reading
        the stale one produces results attributed to a reference that never ran.
        """
        self.assertEqual([], sorted(WORKFLOWS_ROOT.glob("*/mtl_snippets")))
        for compose in sorted(WORKFLOWS_ROOT.glob("*/docker-compose.yml")):
            with self.subTest(compose=compose):
                self.assertNotIn(
                    "/data/snippets",
                    compose.read_text(encoding="utf-8"),
                )

    def test_diagnosis_preparation_imports_in_a_clean_process(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from llm4mtl.semantic_tests.diagnosis_preparation "
                    "import diagnosis_response_dir"
                ),
            ],
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
