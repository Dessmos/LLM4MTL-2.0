"""What the master is asked to run, and what each run mode means.

Two axes are deliberately separate here. ``run_mode`` says which pipeline the
user intends to execute; the stage flags say which components of that pipeline
are enabled or ablated for RQ4. Emulating a mode by disabling flags would make
``full`` with failure diagnosis switched off indistinguishable from
``transformations_only``, and those are different experiments.

The master workflow is authored in the n8n editor, so these tests drive its
shipped ``Validate Config and Build Run Queue``, ``State Machine`` and ``Capture
Action Result`` code under Node instead of restating their rules in Python.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MASTER_WORKFLOW = REPOSITORY_ROOT / "workflows" / "n8n" / "main" / "llm4mtl-agent-workflow.json"
HARNESS = Path(__file__).parent / "fixtures" / "run_master_code_node.js"
TASK_CONTRACTS = REPOSITORY_ROOT / "benchmark" / "tasks"
TRANSFORMATION_WORKFLOW = (
    REPOSITORY_ROOT
    / "workflows"
    / "n8n"
    / "transformations"
    / "workflows"
    / "etl_variants"
    / "Prompting_ETL_gpt-5_few_shots_AND_grammar.json"
)

# What each provider's standard AI Model node looks like once a model is picked
# in its built-in selector. Google keeps the model under a different parameter.
PROVIDER_PARAMS = {
    "OpenAI": {"model": {"value": "gpt-5-2025-08-07"}},
    "Anthropic": {"model": {"value": "claude-sonnet-4-20250514"}},
    "Google Gemini": {"modelName": "models/gemini-2.5-pro"},
}
PROVIDER_FAMILIES = {
    "OpenAI": "gpt-5",
    "Anthropic": "claude-sonnet-4",
    "Google Gemini": "gemini-2-5-pro",
}
PROVIDER_SUFFIX = {
    "OpenAI": "OpenAI Chat Model",
    "Anthropic": "Anthropic Chat Model",
    "Google Gemini": "Google Gemini Chat Model",
}
ROLE_NODES = {
    "transformation": "Transformation Generation",
    "semantic_test": "Semantic Test Generation",
    "source_diagnosis": "Source Diagnosis",
    "refinement": "Refinement",
}
# The card label the form shows, against the id every run records.
STRATEGY_LABELS = {
    "Prompt only": "only_prompt",
    "Few-shot": "few_shot",
    "Grammar": "grammar",
    "Few-shot + Grammar": "few_shots_AND_grammar",
}
STAGE_FIELDS = (
    "test_generation",
    "test_extraction",
    "technical_validation",
    "reference_validation",
    "transformation_generation",
    "syntax_validation",
    "semantic_execution",
    "source_diagnosis",
    "parser_feedback",
    "semantic_feedback",
    "test_refinement",
    "transformation_refinement",
)


def _master() -> dict[str, Any]:
    return json.loads(MASTER_WORKFLOW.read_text(encoding="utf-8"))


def _form_fields() -> list[dict[str, Any]]:
    """The one configuration screen's fields."""
    trigger = next(
        node
        for node in _master()["nodes"]
        if node["type"] == "n8n-nodes-base.formTrigger"
    )
    return trigger["parameters"]["formFields"]["values"]


def _field_options(field_name: str) -> list[str]:
    field = next(
        field for field in _form_fields() if field.get("fieldName") == field_name
    )
    return [option["option"] for option in field["fieldOptions"]["values"]]


def _trigger_type_version() -> float:
    trigger = next(
        node
        for node in _master()["nodes"]
        if node["type"] == "n8n-nodes-base.formTrigger"
    )
    return float(trigger["typeVersion"])


def _submitted_key(field: dict[str, Any], type_version: float) -> str:
    """The json key n8n gives a submitted field.

    This mirrors ``getFieldIdentifier`` in n8n's Form utils: only from
    typeVersion 2.4 does a field arrive under its ``fieldName``. Below that n8n
    keys the item by ``fieldLabel`` — presentation text — and every name the queue
    builder reads arrives undefined. The tests submit through this so they cannot
    pass on keys the real form never sends.
    """
    if type_version >= 2.4 and field.get("fieldName"):
        return field["fieldName"]
    return field.get("fieldLabel") or field.get("fieldName") or ""


def _as_submitted(values: dict[str, Any]) -> dict[str, Any]:
    """Re-key a configuration by what n8n would actually post for this form."""
    version = _trigger_type_version()
    submitted: dict[str, Any] = {}
    for field in _form_fields():
        if field["fieldType"] == "html":
            continue
        name = field["fieldName"]
        if name in values:
            submitted[_submitted_key(field, version)] = values[name]
    missing = set(values) - {field.get("fieldName") for field in _form_fields()}
    assert not missing, f"configuration names no form field: {sorted(missing)}"
    return submitted


def _run_node(
    node: str,
    *,
    inputs: list[dict[str, Any]] | None = None,
    nodes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec = {
        "master": str(MASTER_WORKFLOW),
        "node": node,
        "input": inputs or [],
        "nodes": nodes or {},
    }
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(spec, handle)
        spec_path = handle.name
    try:
        completed = subprocess.run(
            ["node", str(HARNESS), spec_path],
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        Path(spec_path).unlink()
    return json.loads(completed.stdout)


def _model_nodes(unconfigured: tuple[str, ...] = ()) -> dict[str, Any]:
    """Every standard AI Model node on the canvas, as the master reads it.

    A role in ``unconfigured`` has no model picked in any of its provider nodes,
    which is what a user who never touched that role's nodes actually has.
    """
    nodes: dict[str, Any] = {}
    for role, prefix in ROLE_NODES.items():
        for provider, params in PROVIDER_PARAMS.items():
            name = f"{prefix} - {PROVIDER_SUFFIX[provider]}"
            nodes[name] = {"params": {} if role in unconfigured else dict(params)}
    return nodes


def _configure(
    *,
    run_mode: str = "Full Pipeline",
    languages: str = "ETL",
    tasks: dict[str, str] | None = None,
    providers: dict[str, str] | None = None,
    semantic_test_strategy: str = "Few-shot",
    transformation_strategy: str = "Grammar",
    max_test_refinement_iterations: str = "2",
    max_transformation_refinement_iterations: str = "2",
    ablation_profile: str = "Standard full configuration",
    disabled_components: str = "",
    unconfigured_roles: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Submit the configuration screen and build the run queue."""
    chosen = {"etl_tasks": "Tree2Graph", **(tasks or {})}
    provider_choice = {
        "semantic_test_provider": "OpenAI",
        "transformation_provider": "Anthropic",
        "source_diagnosis_provider": "OpenAI",
        "refinement_provider": "Anthropic",
        **(providers or {}),
    }
    return _run_node(
        "Validate Config and Build Run Queue",
        inputs=[
            _as_submitted(
                {
                    "run_mode": run_mode,
                    "languages": languages,
                    **chosen,
                    **provider_choice,
                    "semantic_test_strategy": semantic_test_strategy,
                    "transformation_strategy": transformation_strategy,
                    "max_test_refinement_iterations": max_test_refinement_iterations,
                    "max_transformation_refinement_iterations": (
                        max_transformation_refinement_iterations
                    ),
                    "ablation_profile": ablation_profile,
                    "disabled_components": disabled_components,
                    "n8n_workflow_root": "/data/repository/workflows/n8n",
                }
            )
        ],
        nodes=_model_nodes(unconfigured_roles),
    )


# What each stage reports back when everything succeeds.
PASSING_RESULTS = {
    "create_run": {"run_id": "etl-tree2graph-0001"},
    "generate_tests": {"status": "completed"},
    "extract": {"stage": "extract", "status": "completed", "outcome_code": "EXTRACTED"},
    "technical": {"stage": "technical-validation", "status": "completed", "outcome_code": "TECH_VALID"},
    "reference": {"stage": "reference-validation", "status": "completed", "outcome_code": "REFERENCE_VALIDATED"},
    "generate_transformations": {"status": "completed"},
    "record_generation": {"schema_version": "1.0"},
    "syntax": {"stage": "syntax-validation", "status": "completed", "outcome_code": "SYNTAX_VALID"},
    "execution": {"stage": "execution", "status": "completed", "outcome_code": "SEMANTIC_PASSED"},
    "final": {"artifacts": {}},
}


def _drive(
    config: dict[str, Any],
    results: dict[str, Any] | None = None,
    limit: int = 60,
    factories: dict[str, Any] | None = None,
    observed_states: list[dict[str, Any]] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Run the real control loop until it reaches ``complete``.

    State Machine -> action -> Capture Action Result -> State Machine is the
    orchestration core, so the test walks it rather than a paraphrase.
    """
    stage_results = {**PASSING_RESULTS, **(results or {})}
    state = config
    actions: list[str] = []
    for _ in range(limit):
        machine = _run_node("State Machine", inputs=[state])
        if not machine["ok"]:
            raise AssertionError(machine["error"])
        state = machine["result"]
        if observed_states is not None:
            observed_states.append(state)
        action = state["action"]
        actions.append(action)
        if action == "complete":
            return actions, state
        # A factory lets one action answer differently on each pass, which is how
        # a failing execution becomes a passing one after a refinement.
        factory = (factories or {}).get(action)
        if factory is not None:
            produced = factory()
        elif action == "prepare_refinement":
            artifact_type = state["refinement_request"]["artifact_type"]
            iteration = state["refinement_request"]["iteration"]
            produced = {
                "prompt_path": (
                    f"/data/artifacts/runs/{state['current']['run_id']}/refinements/"
                    f"{artifact_type}/iteration-{iteration:03d}/prompt.md"
                ),
                "request_path": (
                    f"refinements/{artifact_type}/iteration-{iteration:03d}/request.json"
                ),
            }
        else:
            produced = stage_results.get(action, {})
        captured = _run_node(
            "Capture Action Result",
            inputs=[produced],
            nodes={"State Machine": {"json": state}},
        )
        if not captured["ok"]:
            raise AssertionError(captured["error"])
        state = captured["result"]
    raise AssertionError(f"control loop did not terminate: {actions}")


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class OrchestrationFailureTests(unittest.TestCase):
    def test_terminal_result_reports_both_artifact_iterations(self) -> None:
        record = next(
            node
            for node in _master()["nodes"]
            if node["name"] == "Record Terminal Result"
        )
        body = record["parameters"]["jsonBody"]

        self.assertIn("test_iteration:", body)
        self.assertIn("transformation_iteration:", body)
        self.assertIn("max_test_refinement_iterations", body)
        self.assertIn("max_transformation_refinement_iterations", body)

    def test_persistence_http_errors_build_a_terminal_result_request(self) -> None:
        configured = _configure()
        self.assertTrue(configured["ok"], configured.get("error"))
        for action in ("prepare_refinement", "record_generation"):
            with self.subTest(action=action):
                state = json.loads(json.dumps(configured["result"]))
                state["action"] = action
                state["current"]["run_id"] = "terminal-error-1"
                state["current"]["suite_id"] = "terminal-error-1_001"
                state["current"]["test_iteration"] = 1
                state["current"]["transformation_iteration"] = 0
                state["current"]["timeline"] = [
                    {
                        "stage": "reference-validation",
                        "outcome_code": "REFERENCE_VALIDATION_FAILED",
                    }
                ]
                captured = _run_node(
                    "Capture Orchestration Error",
                    inputs=[{"error": {"httpCode": 409}}],
                    nodes={"State Machine": {"json": state}},
                )

                self.assertTrue(captured["ok"], captured.get("error"))
                terminal = captured["result"]["orchestration_terminal_request"]
                self.assertEqual("failed", terminal["status"])
                self.assertEqual(
                    f"ORCHESTRATION_ERROR:{action}", terminal["terminal_state"]
                )
                self.assertEqual(action, terminal["failed_component"])
                self.assertEqual(
                    "reference-validation", terminal["last_completed_stage"]
                )
                self.assertEqual(1, terminal["refinement_iterations_used"])
                self.assertEqual(4, terminal["refinement_iterations_allowed"])
                self.assertEqual(1, terminal["test_iteration"])
                self.assertEqual(0, terminal["transformation_iteration"])

    def test_orchestration_error_reaches_the_shared_final_result_contract(self) -> None:
        configured = _configure()
        self.assertTrue(configured["ok"], configured.get("error"))
        state = configured["result"]
        state["results"] = [
            {
                "run_id": "previous-run",
                "language": "etl",
                "status": "completed",
            }
        ]
        state["action"] = "record_generation"
        state["current"]["run_id"] = "terminal-error-2"
        state["current"]["language"] = "etl"
        state["current"]["task"] = "Tree2Graph"

        captured = _run_node(
            "Capture Orchestration Error",
            inputs=[{"error": {"httpCode": 409}}],
            nodes={"State Machine": {"json": state}},
        )
        self.assertTrue(captured["ok"], captured.get("error"))
        terminal = {
            **captured["result"]["orchestration_terminal_request"],
            "run_id": "terminal-error-2",
        }
        finalized = _run_node(
            "Finalize Orchestration Error",
            inputs=[terminal],
            nodes={"Capture Orchestration Error": {"json": captured["result"]}},
        )
        self.assertTrue(finalized["ok"], finalized.get("error"))
        self.assertEqual(2, len(finalized["result"]["results"]))
        self.assertEqual(
            "terminal-error-2", finalized["result"]["results"][-1]["run_id"]
        )

        summary = _run_node(
            "Final Result and Artifacts", inputs=[finalized["result"]]
        )
        self.assertTrue(summary["ok"], summary.get("error"))
        self.assertEqual("failed", summary["result"]["status"])
        self.assertEqual(2, summary["result"]["run_count"])
        self.assertEqual(terminal, summary["result"]["results"][-1]["artifacts"])


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class TransformationWorkflowCompatibilityTests(unittest.TestCase):
    """The master adapts legacy transformation workflows without editing them."""

    def test_every_external_transformation_workflow_has_adapter_anchors(self) -> None:
        workflows_root = (
            REPOSITORY_ROOT / "workflows" / "n8n" / "transformations" / "workflows"
        )
        workflows = sorted(
            path
            for language in ("etl", "atl", "qvto")
            for path in (workflows_root / f"{language}_variants").glob("Prompting_*.json")
        )
        workflows.append(
            workflows_root
            / "updated_reactions_workflow"
            / "generate_reactions"
            / "LLM4MTL_Generate_Reactions_for_all_Configurations.json"
        )

        for path in workflows:
            with self.subTest(workflow=path):
                nodes = json.loads(path.read_text(encoding="utf-8"))["nodes"]
                prompt_readers = [
                    node for node in nodes if node["name"] == "Read prompt files"
                ]
                response_writers = [
                    node for node in nodes if node["name"] == "Write response to disk"
                ]
                save_names = [
                    node
                    for node in nodes
                    if node["name"] in {"Save file name", "Save reaction name"}
                ]
                self.assertEqual(1, len(prompt_readers))
                self.assertEqual(1, len(response_writers))
                self.assertEqual(
                    "n8n-nodes-base.readWriteFile", response_writers[0]["type"]
                )
                self.assertEqual(1, len(save_names))
                self.assertEqual("n8n-nodes-base.set", save_names[0]["type"])

    def test_every_external_test_workflow_has_generation_adapter_anchors(self) -> None:
        workflows = sorted(
            path
            for path in (
                REPOSITORY_ROOT
                / "workflows"
                / "n8n"
                / "tests"
                / "workflows"
            ).glob("*_variants/test_generation/Prompting_tests_*.json")
            if "qwen2-5-coder-7b" not in path.name
        )
        self.assertTrue(workflows)

        for path in workflows:
            with self.subTest(workflow=path):
                nodes = json.loads(path.read_text(encoding="utf-8"))["nodes"]
                for name in (
                    "Read prompt files",
                    "Write response to disk",
                    "Write prompt to disk",
                ):
                    matched = [node for node in nodes if node["name"] == name]
                    self.assertEqual(1, len(matched), f"{path}: {name}")
                    self.assertEqual("n8n-nodes-base.readWriteFile", matched[0]["type"])

    def test_selected_task_path_and_binary_are_adapted_in_memory(self) -> None:
        original_text = TRANSFORMATION_WORKFLOW.read_text(encoding="utf-8")
        workflow = json.loads(original_text)

        adapted = _run_node(
            "Adapt Transformation Workflow Compatibility",
            inputs=[
                {
                    "action": "generate_transformations",
                    "current": {
                        "language": "etl",
                        "task": "Tree2Graph",
                        "run_id": "run-transform-1",
                        "refinement_iteration": 1,
                    },
                    "subworkflow_input": {
                        "refinement_iteration": 1,
                        "prompt_path": "/data/artifacts/runs/run-transform-1/refinements/transformation/iteration-001/prompt.md",
                    },
                    "workflow_json": workflow,
                }
            ],
        )

        self.assertTrue(adapted["ok"], adapted.get("error"))
        nodes = {
            node["name"]: node
            for node in adapted["result"]["workflow_json"]["nodes"]
        }
        self.assertEqual(
            "=/data/artifacts/runs/run-transform-1/refinements/"
            "transformation/iteration-001/prompt.md",
            nodes["Read prompt files"]["parameters"]["fileSelector"],
        )
        self.assertEqual(
            "={{ $json.prompt }}",
            nodes["(Re-)Generate code"]["parameters"]["text"],
        )
        save_name = nodes["Save file name"]
        base_name = next(
            assignment
            for assignment in save_name["parameters"]["assignments"]["assignments"]
            if assignment["name"] == "baseName"
        )
        self.assertEqual("=Tree2Graph", base_name["value"])
        self.assertTrue(save_name["parameters"]["includeOtherFields"])
        self.assertFalse(save_name["parameters"]["options"]["stripBinary"])
        self.assertEqual(
            "=/data/artifacts/runs/run-transform-1/responses/"
            "transformation-generation/iteration-001/Tree2Graph.etl",
            nodes["Write response to disk"]["parameters"]["fileName"],
        )
        self.assertEqual(
            original_text,
            TRANSFORMATION_WORKFLOW.read_text(encoding="utf-8"),
        )

    def test_selected_semantic_test_task_and_response_are_run_scoped(self) -> None:
        workflow_path = (
            REPOSITORY_ROOT
            / "workflows"
            / "n8n"
            / "tests"
            / "workflows"
            / "etl_variants"
            / "test_generation"
            / "Prompting_tests_ETL_gpt-5_few_shot.json"
        )
        original_text = workflow_path.read_text(encoding="utf-8")
        workflow = json.loads(original_text)

        adapted = _run_node(
            "Adapt Transformation Workflow Compatibility",
            inputs=[
                {
                    "action": "generate_tests",
                    "current": {
                        "language": "etl",
                        "task": "Tree2Graph",
                        "run_id": "run-tests-1",
                        "refinement_iteration": 2,
                    },
                    "subworkflow_input": {
                        "refinement_iteration": 2,
                        "prompt_path": "/data/artifacts/runs/run-tests-1/refinements/semantic-test/iteration-002/prompt.md",
                    },
                    "workflow_json": workflow,
                }
            ],
        )
        self.assertTrue(adapted["ok"], adapted.get("error"))
        nodes = {
            node["name"]: node
            for node in adapted["result"]["workflow_json"]["nodes"]
        }
        self.assertEqual(
            "=/data/artifacts/runs/run-tests-1/refinements/"
            "semantic-test/iteration-002/prompt.md",
            nodes["Read prompt files"]["parameters"]["fileSelector"],
        )
        self.assertEqual(
            "={{ $json.prompt }}",
            nodes["(Re-)Generate test suite"]["parameters"]["text"],
        )
        self.assertEqual(
            "=/data/artifacts/runs/run-tests-1/responses/"
            "semantic-test-generation/iteration-002/Tree2Graph.md",
            nodes["Write response to disk"]["parameters"]["fileName"],
        )
        self.assertEqual(
            original_text,
            workflow_path.read_text(encoding="utf-8"),
        )

    def test_initial_semantic_test_writes_only_to_the_prepared_run_directory(
        self,
    ) -> None:
        workflow_path = (
            REPOSITORY_ROOT
            / "workflows"
            / "n8n"
            / "tests"
            / "workflows"
            / "etl_variants"
            / "test_generation"
            / "Prompting_tests_ETL_gpt-5_few_shot.json"
        )
        workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

        adapted = _run_node(
            "Adapt Transformation Workflow Compatibility",
            inputs=[
                {
                    "action": "generate_tests",
                    "current": {
                        "language": "etl",
                        "task": "Tree2Graph",
                        "run_id": "run-tests-initial",
                        "refinement_iteration": 0,
                    },
                    "subworkflow_input": {"refinement_iteration": 0},
                    "workflow_json": workflow,
                }
            ],
        )

        self.assertTrue(adapted["ok"], adapted.get("error"))
        nodes = {
            node["name"]: node
            for node in adapted["result"]["workflow_json"]["nodes"]
        }
        response_directory = (
            "=/data/artifacts/runs/run-tests-initial/responses/"
            "semantic-test-generation/iteration-000"
        )
        self.assertEqual(
            "=/data/task_prompts/etl/Tree2Graph.txt",
            nodes["Read prompt files"]["parameters"]["fileSelector"],
        )
        self.assertEqual(
            f"{response_directory}/prompt.md",
            nodes["Write prompt to disk"]["parameters"]["fileName"],
        )
        self.assertEqual(
            f"{response_directory}/Tree2Graph.md",
            nodes["Write response to disk"]["parameters"]["fileName"],
        )

    def test_non_generation_subworkflows_are_not_modified(self) -> None:
        workflow = {
            "nodes": [{"name": "Diagnosis", "parameters": {}}],
            "connections": {},
        }
        adapted = _run_node(
            "Adapt Transformation Workflow Compatibility",
            inputs=[
                {
                    "action": "diagnose",
                    "current": {"language": "etl", "task": "Tree2Graph"},
                    "workflow_json": workflow,
                }
            ],
        )
        self.assertTrue(adapted["ok"], adapted.get("error"))
        self.assertEqual(workflow, adapted["result"]["workflow_json"])


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class RunModeTests(unittest.TestCase):
    def test_tests_only_never_routes_into_transformation_generation(self) -> None:
        config = _configure(run_mode="Semantic Tests Only")
        self.assertTrue(config["ok"], config.get("error"))
        actions, state = _drive(config["result"])
        for action in ("generate_transformations", "syntax", "execution", "diagnose"):
            self.assertNotIn(action, actions)
        self.assertEqual(
            ["create_run", "generate_tests", "record_generation", "extract", "technical", "reference", "final", "complete"],
            actions,
        )
        self.assertEqual("completed", state["results"][0]["status"])
        self.assertEqual("TESTS_ONLY_PIPELINE_COMPLETE", state["results"][0]["reason"])

    def test_transformations_only_never_routes_into_test_generation(self) -> None:
        config = _configure(run_mode="Transformations Only")
        self.assertTrue(config["ok"], config.get("error"))
        actions, state = _drive(config["result"])
        for action in ("generate_tests", "extract", "technical", "reference", "execution", "diagnose"):
            self.assertNotIn(action, actions)
        self.assertEqual(
            ["create_run", "generate_transformations", "record_generation", "syntax", "final", "complete"],
            actions,
        )
        self.assertEqual("completed", state["results"][0]["status"])
        self.assertEqual(
            "TRANSFORMATIONS_ONLY_PIPELINE_COMPLETE", state["results"][0]["reason"]
        )

    def test_full_reaches_both_branches_and_semantic_execution(self) -> None:
        config = _configure(run_mode="Full Pipeline")
        self.assertTrue(config["ok"], config.get("error"))
        actions, state = _drive(config["result"])
        self.assertEqual(
            [
                "create_run",
                "generate_tests",
                "record_generation",
                "extract",
                "technical",
                "reference",
                "generate_transformations",
                "record_generation",
                "syntax",
                "execution",
                "final",
                "complete",
            ],
            actions,
        )
        self.assertEqual("completed", state["results"][0]["status"])
        self.assertEqual("SEMANTIC_PASSED", state["results"][0]["reason"])

    def test_full_diagnoses_a_semantic_failure_and_refines(self) -> None:
        actions, _ = _drive_diagnosis(["transformation_defect"])
        self.assertIn("read_diagnosis_index", actions)
        self.assertIn("diagnose", actions)
        # The diagnosed transformation defect sends the run back through
        # transformation generation rather than test generation.
        self.assertEqual("prepare_refinement", actions[actions.index("diagnose") + 1])
        self.assertEqual("generate_transformations", actions[actions.index("diagnose") + 2])

    def test_a_failure_without_a_prepared_index_says_so(self) -> None:
        """The shortcut report alone is no longer enough to diagnose on."""
        config = _configure(run_mode="Full Pipeline")
        _, state = _drive(
            config["result"],
            results={
                "execution": {
                    "stage": "execution",
                    "status": "completed",
                    "outcome_code": "SEMANTIC_EXECUTION_FAILED",
                    "artifacts": {"failure_report_path": "artifacts/work/runs/x/r.json"},
                }
            },
        )
        result = state["results"][0]
        self.assertEqual("incomplete", result["status"])
        self.assertEqual("SOURCE_DIAGNOSIS_EVIDENCE_NOT_EXPOSED", result["reason"])

    def test_disabled_semantic_feedback_cannot_reach_diagnosis_or_refinement(
        self,
    ) -> None:
        config = _configure(ablation_profile="No semantic feedback")
        self.assertTrue(config["ok"], config.get("error"))
        actions, state = _drive(
            config["result"],
            results={"execution": _failing_execution()},
        )

        self.assertNotIn("read_diagnosis_index", actions)
        self.assertNotIn("diagnose", actions)
        self.assertNotIn("prepare_refinement", actions)
        self.assertEqual(
            "SEMANTIC_EXECUTION_FAILED:SEMANTIC_FEEDBACK_DISABLED",
            state["results"][0]["reason"],
        )

    def test_every_run_mode_has_a_successful_terminal_path(self) -> None:
        for mode in ("Semantic Tests Only", "Transformations Only", "Full Pipeline"):
            with self.subTest(mode=mode):
                config = _configure(run_mode=mode)
                self.assertTrue(config["ok"], config.get("error"))
                _, state = _drive(config["result"])
                self.assertEqual("completed", state["results"][0]["status"])


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class RefinementOutcomeRoutingTests(unittest.TestCase):
    def test_test_failures_share_one_target_budget_and_keep_their_source(self) -> None:
        cases = (
            ("extract", "TEST_SPEC_INVALID", "technical", "technical_refinement"),
            ("technical", "TECH_COMPILE_FAILED", "technical", "technical_refinement"),
            (
                "reference",
                "REFERENCE_VALIDATION_FAILED",
                "reference",
                "reference_refinement",
            ),
        )
        for action, outcome_code, source, purpose in cases:
            with self.subTest(action=action, outcome_code=outcome_code):
                calls = 0

                def fail_once() -> dict[str, Any]:
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        return {
                            "stage": PASSING_RESULTS[action]["stage"],
                            "status": "completed",
                            "outcome_code": outcome_code,
                        }
                    return PASSING_RESULTS[action]

                configured = _configure()
                self.assertTrue(configured["ok"], configured.get("error"))
                _, state = _drive(
                    configured["result"],
                    factories={action: fail_once},
                )
                refined = next(
                    entry
                    for entry in state["results"][0]["timeline"]
                    if entry.get("action") == "generate_tests"
                    and entry.get("refinement_iteration") == 1
                )

                self.assertEqual("tests", refined["refinement_target"])
                self.assertEqual(source, refined["refinement_source"])
                self.assertEqual(purpose, refined["purpose"])

    def test_syntax_failure_routes_to_transformation_refinement(self) -> None:
        calls = 0

        def fail_once() -> dict[str, Any]:
            nonlocal calls
            calls += 1
            if calls == 1:
                return {
                    "stage": "syntax-validation",
                    "status": "completed",
                    "outcome_code": "SYNTAX_INVALID",
                }
            return PASSING_RESULTS["syntax"]

        configured = _configure()
        self.assertTrue(configured["ok"], configured.get("error"))
        _, state = _drive(
            configured["result"],
            factories={"syntax": fail_once},
        )
        refined = next(
            entry
            for entry in state["results"][0]["timeline"]
            if entry.get("action") == "generate_transformations"
            and entry.get("refinement_iteration") == 1
        )

        self.assertEqual("transformations", refined["refinement_target"])
        self.assertEqual("syntax", refined["refinement_source"])
        self.assertEqual("syntax_refinement", refined["purpose"])


def _diagnosis_index(*reports: dict[str, Any]) -> dict[str, Any]:
    """One prepared attempt's index, shaped as diagnosis_preparation writes it."""
    return {
        "eligible_reports": [
            {
                "failure_report_path": report["path"],
                "scope": report.get("scope", "test_case"),
                "reason": "parser_passed_and_semantic_test_failed",
                "test_case_id": report.get("test_case_id", "case-1"),
                "assertion_id": report.get("assertion_id", "assertion-001"),
                "suite": "suite_001",
                "transformation": "generated.atl",
            }
            for report in reports
        ],
        "eligible_count": len(reports),
        "diagnosis_eligible_declared": len(reports),
    }


def _failing_execution() -> dict[str, Any]:
    return {
        "stage": "execution",
        "status": "completed",
        "outcome_code": "SEMANTIC_EXECUTION_FAILED",
        "attempt": 1,
        "artifacts": {
            "failure_report_index": (
                "artifacts/work/runs/etl-tree2graph-0001/diagnosis/execution/"
                "attempt-001/index.json"
            ),
            "failure_report_path": (
                "artifacts/work/runs/etl-tree2graph-0001/diagnosis/execution/"
                "attempt-001/reports/first.json"
            ),
        },
    }


def _drive_diagnosis(
    classifications: list[str],
    *,
    eligible: int | None = None,
    verdicts: list[dict[str, Any]] | None = None,
    observed_states: list[dict[str, Any]] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """A full-mode run whose first execution fails with N eligible reports.

    The second execution passes, so the run terminates and the action counts are
    the counts of one diagnosis round rather than of a refinement loop.
    """
    count = len(classifications) if eligible is None else eligible
    reports = [
        {
            "path": "artifacts/work/runs/etl-tree2graph-0001/diagnosis/execution/"
            f"attempt-001/reports/r{index}.json"
        }
        for index in range(count)
    ]
    supplied = verdicts if verdicts is not None else [
        {
            "classification": value,
            "confidence": "high",
            "test_case_id": "case-1",
            "assertion_id": "assertion-001",
        }
        for value in classifications
    ]
    calls = {"diagnose": 0, "execution": 0}

    def next_verdict() -> dict[str, Any]:
        index = calls["diagnose"]
        calls["diagnose"] += 1
        return supplied[index] if index < len(supplied) else {}

    def next_execution() -> dict[str, Any]:
        calls["execution"] += 1
        if calls["execution"] == 1:
            return _failing_execution()
        return PASSING_RESULTS["execution"]

    config = _configure(run_mode="Full Pipeline")
    assert config["ok"], config.get("error")
    return _drive(
        config["result"],
        {"read_diagnosis_index": _diagnosis_index(*reports)},
        factories={"diagnose": next_verdict, "execution": next_execution},
        observed_states=observed_states,
    )


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class SourceDiagnosisAggregationTests(unittest.TestCase):
    """Every eligible report is diagnosed, and the verdicts combine conservatively.

    An execution attempt can fail several suite/transformation pairs at once, and
    the pairs need not agree. Repairing the transformation because the first
    report happened to blame it, while another report blamed the test, is exactly
    the mistake source diagnosis exists to prevent - so a mixed or ambiguous set
    is ambiguous, never a majority vote.
    """

    def test_one_transformation_defect_refines_the_transformation(self) -> None:
        actions, state = _drive_diagnosis(["transformation_defect"])
        self.assertEqual(1, actions.count("diagnose"))
        self.assertEqual("prepare_refinement", actions[actions.index("diagnose") + 1])
        self.assertEqual("generate_transformations", actions[actions.index("diagnose") + 2])

    def test_agreeing_transformation_defects_refine_the_transformation(self) -> None:
        actions, _ = _drive_diagnosis(["transformation_defect", "transformation_defect"])
        self.assertEqual(2, actions.count("diagnose"))
        last = len(actions) - 1 - actions[::-1].index("diagnose")
        self.assertEqual("prepare_refinement", actions[last + 1])
        self.assertEqual("generate_transformations", actions[last + 2])

    def test_one_test_defect_refines_the_tests(self) -> None:
        actions, _ = _drive_diagnosis(["test_defect"])
        self.assertEqual("prepare_refinement", actions[actions.index("diagnose") + 1])
        self.assertEqual("generate_tests", actions[actions.index("diagnose") + 2])

    def test_semantic_refinement_request_names_its_execution_attempt(self) -> None:
        observed: list[dict[str, Any]] = []
        _drive_diagnosis(["test_defect"], observed_states=observed)
        request = next(
            state["refinement_request"]
            for state in observed
            if state["action"] == "prepare_refinement"
        )
        self.assertEqual(1, request["execution_attempt"])

    def test_refinement_trajectory_names_target_and_feedback_source(self) -> None:
        _, state = _drive_diagnosis(["test_defect"])
        refined_generation = next(
            entry
            for entry in state["results"][0]["timeline"]
            if entry.get("action") == "generate_tests"
            and entry.get("refinement_iteration") == 1
        )

        self.assertEqual("tests", refined_generation["refinement_target"])
        self.assertEqual("semantic", refined_generation["refinement_source"])

    def test_agreeing_test_defects_refine_the_tests(self) -> None:
        actions, _ = _drive_diagnosis(["test_defect", "test_defect"])
        self.assertEqual(2, actions.count("diagnose"))
        last = len(actions) - 1 - actions[::-1].index("diagnose")
        self.assertEqual("prepare_refinement", actions[last + 1])
        self.assertEqual("generate_tests", actions[last + 2])

    def test_a_refined_transformation_keeps_the_validated_suite(self) -> None:
        """Only a refined *suite* is a new suite.

        A refined transformation is judged against the suite that already passed
        on the reference — that pairing is what makes its failure evidence about
        the transformation. Renaming the suite here left the execution stage
        selecting a suite id that never existed, so it evaluated nothing and
        every transformation refinement ended in an infrastructure error.
        """
        _, state = _drive_diagnosis(["transformation_defect"])
        result = state["results"][0]

        self.assertEqual(1, result["refinement_iterations"])
        self.assertEqual("etl-tree2graph-0001_000", result["suite_id"])

    def test_a_refined_suite_gets_its_own_id(self) -> None:
        _, state = _drive_diagnosis(["test_defect"])
        result = state["results"][0]

        self.assertEqual(1, result["refinement_iterations"])
        self.assertEqual("etl-tree2graph-0001_001", result["suite_id"])

    def test_test_refinement_does_not_invent_a_transformation_iteration(self) -> None:
        """A new suite is executed against the transformation already generated."""
        _, state = _drive_diagnosis(["test_defect"])
        syntax_attempts = [
            entry
            for entry in state["results"][0]["timeline"]
            if entry.get("action") == "syntax"
        ]

        self.assertEqual(
            [0],
            [entry["refinement_iteration"] for entry in syntax_attempts],
        )

    def test_test_budget_cannot_exhaust_transformation_budget(self) -> None:
        reference_calls = 0
        execution_calls = 0

        def reference_result() -> dict[str, Any]:
            nonlocal reference_calls
            reference_calls += 1
            if reference_calls <= 2:
                return {
                    "stage": "reference-validation",
                    "status": "completed",
                    "outcome_code": "REFERENCE_VALIDATION_FAILED",
                }
            return PASSING_RESULTS["reference"]

        def execution_result() -> dict[str, Any]:
            nonlocal execution_calls
            execution_calls += 1
            if execution_calls == 1:
                return _failing_execution()
            return PASSING_RESULTS["execution"]

        configured = _configure(
            max_test_refinement_iterations="2",
            max_transformation_refinement_iterations="1",
        )
        self.assertTrue(configured["ok"], configured.get("error"))
        actions, state = _drive(
            configured["result"],
            results={
                "read_diagnosis_index": _diagnosis_index(
                    {
                        "path": (
                            "artifacts/work/runs/etl-tree2graph-0001/diagnosis/"
                            "execution/attempt-001/reports/r0.json"
                        )
                    }
                )
            },
            factories={
                "reference": reference_result,
                "execution": execution_result,
                "diagnose": lambda: {
                    "classification": "transformation_defect",
                    "confidence": "high",
                    "test_case_id": "case-1",
                    "assertion_id": "assertion-001",
                },
            },
        )

        result = state["results"][0]
        self.assertEqual("completed", result["status"])
        self.assertEqual(2, result["test_refinement_iterations"])
        self.assertEqual(1, result["transformation_refinement_iterations"])
        self.assertEqual(3, result["refinement_iterations"])
        self.assertEqual(3, actions.count("prepare_refinement"))

    def test_unknown_refinement_reason_is_an_orchestration_error(self) -> None:
        configured = _configure()
        self.assertTrue(configured["ok"], configured.get("error"))
        state = configured["result"]
        state["current"]["run_id"] = "unknown-refinement-reason"
        state["current"]["test_iteration"] = 1
        state["current"]["refinement_reason"] = "UNRECOGNIZED_TEST_FAILURE"
        state["subworkflow_input"] = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "strategy": "few_shot",
        }
        state["completed_action"] = "generate_tests"
        state["last_result"] = {"status": "completed"}

        routed = _run_node("State Machine", inputs=[state])

        self.assertFalse(routed["ok"])
        self.assertIn("Unknown refinement reason", routed["error"])

    def test_transformation_refinement_keeps_the_test_iteration(self) -> None:
        """A refined transformation stays paired with the validated suite."""
        _, state = _drive_diagnosis(["transformation_defect"])
        syntax_attempts = [
            entry
            for entry in state["results"][0]["timeline"]
            if entry.get("action") == "syntax"
        ]

        self.assertEqual(
            [0, 1],
            [entry["refinement_iteration"] for entry in syntax_attempts],
        )
        self.assertEqual("etl-tree2graph-0001_000", state["results"][0]["suite_id"])

    def test_test_refinement_does_not_change_the_initial_transformation_model(self) -> None:
        """Artifact-specific iterations select provider and model as one pair."""
        reference_calls = 0

        def reference_result() -> dict[str, Any]:
            nonlocal reference_calls
            reference_calls += 1
            if reference_calls == 1:
                return {
                    "stage": "reference-validation",
                    "status": "completed",
                    "outcome_code": "REFERENCE_VALIDATION_FAILED",
                }
            return PASSING_RESULTS["reference"]

        configured = _configure(
            run_mode="Full Pipeline",
            providers={"refinement_provider": "Google Gemini"},
        )
        self.assertTrue(configured["ok"], configured.get("error"))
        observed: list[dict[str, Any]] = []
        _, final_state = _drive(
            configured["result"],
            factories={"reference": reference_result},
            observed_states=observed,
        )
        initial_transformation = next(
            state
            for state in observed
            if state["action"] == "generate_transformations"
        )

        self.assertEqual(0, initial_transformation["current"]["transformation_iteration"])
        self.assertEqual(
            initial_transformation["config"]["llms"]["transformation"]["provider"],
            initial_transformation["subworkflow_input"]["provider"],
        )
        self.assertEqual(
            initial_transformation["config"]["llms"]["transformation"]["model"],
            initial_transformation["subworkflow_input"]["model"],
        )
        transformation_generation = next(
            entry
            for entry in final_state["results"][0]["timeline"]
            if entry["action"] == "generate_transformations"
        )
        self.assertEqual("initial", transformation_generation["purpose"])

    def test_a_mixed_set_is_ambiguous_and_refines_nothing(self) -> None:
        actions, state = _drive_diagnosis(["transformation_defect", "test_defect"])
        self.assertEqual(2, actions.count("diagnose"))
        result = state["results"][0]
        self.assertEqual("completed_with_failures", result["status"])
        self.assertEqual("AMBIGUOUS_SOURCE_DIAGNOSIS", result["reason"])
        self.assertNotIn("generate_transformations", actions[actions.index("diagnose") :])

    def test_one_ambiguous_verdict_makes_the_whole_set_ambiguous(self) -> None:
        for others in (["transformation_defect"], ["test_defect"]):
            with self.subTest(others=others):
                actions, state = _drive_diagnosis([*others, "ambiguous"])
                result = state["results"][0]
                self.assertEqual("completed_with_failures", result["status"])
                self.assertEqual("AMBIGUOUS_SOURCE_DIAGNOSIS", result["reason"])

    def test_a_majority_never_outvotes_a_dissenting_report(self) -> None:
        """T, T, X is ambiguous - the evidence still says a test may be at fault."""
        actions, state = _drive_diagnosis(
            ["transformation_defect", "transformation_defect", "test_defect"]
        )
        self.assertEqual(3, actions.count("diagnose"))
        self.assertEqual("AMBIGUOUS_SOURCE_DIAGNOSIS", state["results"][0]["reason"])

    def test_every_eligible_report_is_diagnosed_not_only_the_first(self) -> None:
        """The regression this whole stage exists for.

        Python's index names every diagnosable report and also offers
        ``failure_report_path`` as a shortcut to the first one. Routing on the
        shortcut decided a refinement from one failure while the attempt had
        recorded several.
        """
        actions, state = _drive_diagnosis(
            ["transformation_defect", "transformation_defect", "transformation_defect"]
        )
        self.assertEqual(3, actions.count("diagnose"))
        verdicts = state["results"][0]["timeline"]
        diagnosed = [entry for entry in verdicts if entry.get("action") == "diagnose"]
        self.assertEqual(3, len(diagnosed))
        # Each invocation named its own report, so no report was diagnosed twice.
        paths = [entry["failure_report_path"] for entry in diagnosed]
        self.assertEqual(3, len(set(paths)), paths)

    def test_every_individual_verdict_is_recorded(self) -> None:
        actions, state = _drive_diagnosis(["transformation_defect", "test_defect"])
        timeline = state["results"][0]["timeline"]
        diagnosed = [entry for entry in timeline if entry.get("action") == "diagnose"]
        self.assertEqual(
            ["transformation_defect", "test_defect"],
            [entry["classification"] for entry in diagnosed],
        )
        aggregated = [entry for entry in timeline if entry.get("action") == "aggregate_diagnosis"]
        self.assertEqual(1, len(aggregated))
        self.assertEqual("ambiguous", aggregated[0]["aggregate"])
        self.assertEqual(
            ["transformation_defect", "test_defect"], aggregated[0]["classifications"]
        )

    def test_no_eligible_report_gets_an_explicit_terminal_reason(self) -> None:
        actions, state = _drive_diagnosis([], eligible=0)
        self.assertNotIn("diagnose", actions)
        result = state["results"][0]
        self.assertEqual("completed_with_failures", result["status"])
        self.assertEqual("NO_ELIGIBLE_SOURCE_DIAGNOSIS_REPORTS", result["reason"])

    def test_a_failed_invocation_never_aggregates_a_partial_set(self) -> None:
        """Two verdicts out of three decide nothing."""
        actions, state = _drive_diagnosis(
            ["transformation_defect", "transformation_defect", "transformation_defect"],
            verdicts=[
                {"classification": "transformation_defect", "confidence": "high"},
                {"classification": "transformation_defect", "confidence": "high"},
                {},
            ],
        )
        result = state["results"][0]
        self.assertEqual("incomplete", result["status"])
        self.assertEqual("INCOMPLETE_SOURCE_DIAGNOSIS_SET", result["reason"])
        self.assertNotIn("generate_transformations", actions[actions.index("diagnose") :])


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class RunQueueTests(unittest.TestCase):
    def test_the_queue_is_the_selected_languages_and_tasks(self) -> None:
        config = _configure(
            languages="ETL,QVT-O",
            tasks={"etl_tasks": "OO2DB,rss2atom", "qvto_tasks": "ModelExtents"},
        )
        self.assertTrue(config["ok"], config.get("error"))
        queue = [(spec["language"], spec["task"]) for spec in config["result"]["run_specs"]]
        self.assertEqual(
            [("etl", "OO2DB"), ("etl", "rss2atom"), ("qvto", "ModelExtents")], queue
        )

    def test_no_hidden_default_task_survives_an_explicit_selection(self) -> None:
        """The old master ran Tree2Graph for ETL whatever the user asked for."""
        config = _configure(languages="ETL", tasks={"etl_tasks": "greedy"})
        tasks = [spec["task"] for spec in config["result"]["run_specs"]]
        self.assertEqual(["greedy"], tasks)
        self.assertNotIn("Tree2Graph", tasks)

    def test_a_selected_language_without_a_task_is_refused(self) -> None:
        config = _configure(languages="ETL,ATL", tasks={"atl_tasks": ""})
        self.assertFalse(config["ok"])
        self.assertIn("at least one task for atl", config["error"])

    def test_the_form_offers_exactly_the_benchmark_task_contracts(self) -> None:
        """The form's task names are static, so they are held to the benchmark.

        n8n form fields carry their options in the workflow JSON. Adding a task
        contract without adding it here would silently make it unselectable, so
        the two are asserted equal rather than left to drift.
        """
        for language in ("etl", "atl", "qvto", "reactions"):
            with self.subTest(language=language):
                contracts = sorted(
                    path.stem
                    for path in (TASK_CONTRACTS / language / "task_contracts").glob("*.json")
                )
                self.assertEqual(contracts, sorted(_field_options(f"{language}_tasks")))


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class ConditionalLlmRoleTests(unittest.TestCase):
    def test_tests_only_does_not_require_a_transformation_model(self) -> None:
        config = _configure(
            run_mode="Semantic Tests Only",
            unconfigured_roles=("transformation", "source_diagnosis"),
        )
        self.assertTrue(config["ok"], config.get("error"))
        llms = config["result"]["config"]["llms"]
        self.assertNotIn("transformation", llms)
        self.assertNotIn("source_diagnosis", llms)
        self.assertIn("semantic_test", llms)
        spec = config["result"]["run_specs"][0]
        self.assertIsNone(spec["transformation_model"])
        self.assertIsNone(spec["transformation_strategy"])

    def test_transformations_only_does_not_require_a_test_generation_model(self) -> None:
        config = _configure(
            run_mode="Transformations Only",
            unconfigured_roles=("semantic_test", "source_diagnosis"),
        )
        self.assertTrue(config["ok"], config.get("error"))
        llms = config["result"]["config"]["llms"]
        self.assertNotIn("semantic_test", llms)
        self.assertIn("transformation", llms)
        self.assertIsNone(config["result"]["run_specs"][0]["test_generation_model"])

    def test_a_reachable_role_still_fails_when_its_model_node_is_empty(self) -> None:
        config = _configure(
            run_mode="Semantic Tests Only",
            unconfigured_roles=("semantic_test",),
        )
        self.assertFalse(config["ok"])
        self.assertIn(
            "Select a model in the built-in selector of "
            "Semantic Test Generation - OpenAI Chat Model",
            config["error"],
        )

    def test_disabling_diagnosis_removes_its_model_requirement(self) -> None:
        config = _configure(
            ablation_profile="No failure diagnosis",
            unconfigured_roles=("source_diagnosis",),
        )
        self.assertTrue(config["ok"], config.get("error"))
        self.assertNotIn("source_diagnosis", config["result"]["config"]["llms"])

    def test_zero_refinement_iterations_remove_the_refinement_requirement(self) -> None:
        config = _configure(
            max_test_refinement_iterations="0",
            max_transformation_refinement_iterations="0",
            unconfigured_roles=("refinement",),
        )
        self.assertTrue(config["ok"], config.get("error"))
        self.assertNotIn("refinement", config["result"]["config"]["llms"])

    def test_a_reachable_refinement_role_is_still_required(self) -> None:
        config = _configure(unconfigured_roles=("refinement",))
        self.assertFalse(config["ok"])
        self.assertIn("Refinement - Anthropic Chat Model", config["error"])

    def test_the_resolved_model_comes_from_the_standard_ai_model_node(self) -> None:
        """Provider is chosen in the form; the exact model is read off the canvas."""
        config = _configure(providers={"semantic_test_provider": "Google Gemini"})
        semantic_test = config["result"]["config"]["llms"]["semantic_test"]
        self.assertEqual("google", semantic_test["provider"])
        self.assertEqual("models/gemini-2.5-pro", semantic_test["model"])
        self.assertEqual("gemini-2-5-pro", semantic_test["artifact_model"])
        self.assertEqual(
            "Semantic Test Generation - Google Gemini Chat Model",
            semantic_test["configuration_node"],
        )

    def test_python_receives_the_family_while_n8n_keeps_the_exact_model(self) -> None:
        """Filesystem selection and provider invocation use distinct identities."""
        for provider, family in PROVIDER_FAMILIES.items():
            with self.subTest(provider=provider):
                configured = PROVIDER_PARAMS[provider]
                raw_model = configured.get("model") or configured["modelName"]
                exact_model = (
                    raw_model["value"] if isinstance(raw_model, dict) else raw_model
                )
                config = _configure(
                    run_mode="Semantic Tests Only",
                    providers={"semantic_test_provider": provider},
                    max_test_refinement_iterations="0",
                    max_transformation_refinement_iterations="0",
                )
                self.assertTrue(config["ok"], config.get("error"))
                state = config["result"]
                semantic_test = state["config"]["llms"]["semantic_test"]
                self.assertEqual(exact_model, semantic_test["model"])
                self.assertEqual(family, semantic_test["artifact_model"])
                self.assertEqual(
                    family,
                    state["run_specs"][0]["test_generation_model"],
                )

                create_run = _run_node("State Machine", inputs=[state])
                self.assertTrue(create_run["ok"], create_run.get("error"))
                captured = _run_node(
                    "Capture Action Result",
                    inputs=[{"run_id": "etl-tree2graph-family-test"}],
                    nodes={"State Machine": {"json": create_run["result"]}},
                )
                self.assertTrue(captured["ok"], captured.get("error"))
                generate_tests = _run_node(
                    "State Machine", inputs=[captured["result"]]
                )
                self.assertTrue(generate_tests["ok"], generate_tests.get("error"))
                self.assertEqual("generate_tests", generate_tests["result"]["action"])
                self.assertEqual(
                    exact_model,
                    generate_tests["result"]["subworkflow_input"]["model"],
                )


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class AblationIdentityTests(unittest.TestCase):
    def test_an_ablated_full_run_is_not_a_transformations_only_run(self) -> None:
        ablated = _configure(ablation_profile="No failure diagnosis")["result"]["config"]
        narrowed = _configure(run_mode="Transformations Only")["result"]["config"]

        self.assertEqual("full", ablated["run_mode"])
        self.assertFalse(ablated["stages"]["source_diagnosis"])
        self.assertEqual("full:no-failure-diagnosis", ablated["pipeline_variant"])

        self.assertEqual("transformations_only", narrowed["run_mode"])
        self.assertTrue(narrowed["stages"]["source_diagnosis"])
        self.assertEqual("transformations_only", narrowed["pipeline_variant"])

        self.assertNotEqual(ablated["pipeline_variant"], narrowed["pipeline_variant"])

    def test_a_standard_full_run_keeps_the_recorded_variant_id(self) -> None:
        config = _configure()["result"]["config"]
        self.assertEqual("full", config["pipeline_variant"])
        self.assertEqual([], config["disabled_stages"])
        self.assertTrue(all(config["stages"][stage] for stage in STAGE_FIELDS))

    def test_a_custom_ablation_names_every_disabled_component(self) -> None:
        config = _configure(
            ablation_profile="Custom ablation",
            disabled_components="reference_validation,parser_feedback",
        )["result"]["config"]
        self.assertEqual(
            ["reference_validation", "parser_feedback"], config["disabled_stages"]
        )
        self.assertEqual(
            "full:custom:reference_validation+parser_feedback", config["pipeline_variant"]
        )
        self.assertFalse(config["stages"]["reference_validation"])
        self.assertFalse(config["stages"]["parser_feedback"])

    def test_a_named_profile_refuses_an_extra_component_selection(self) -> None:
        """An ablation the variant id does not name would be a silent one."""
        config = _configure(
            ablation_profile="No parser feedback",
            disabled_components="semantic_execution",
        )
        self.assertFalse(config["ok"])
        self.assertIn("Custom ablation", config["error"])

    def test_every_component_flag_is_still_expressible(self) -> None:
        config = _configure(
            ablation_profile="Custom ablation",
            disabled_components=",".join(STAGE_FIELDS),
        )["result"]["config"]
        self.assertEqual(list(STAGE_FIELDS), config["disabled_stages"])
        self.assertTrue(not any(config["stages"][stage] for stage in STAGE_FIELDS))

    def test_the_form_offers_every_component_flag_for_custom_ablation(self) -> None:
        self.assertEqual(
            sorted(STAGE_FIELDS), sorted(_field_options("disabled_components"))
        )

    def test_run_mode_and_stage_flags_stay_separate_in_the_config(self) -> None:
        config = _configure(run_mode="Semantic Tests Only")["result"]["config"]
        # The mode narrows what executes; it does not pretend the transformation
        # components were ablated.
        self.assertEqual("tests_only", config["run_mode"])
        self.assertTrue(config["stages"]["transformation_generation"])
        self.assertTrue(config["stages"]["syntax_validation"])


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class ConfigurationPresentationTests(unittest.TestCase):
    """The cards are presentation; the recorded values are the canonical ids.

    Every option is a native n8n radio or checkbox styled as a card, so the
    submitted value is still the field value n8n would submit unstyled. What the
    form calls a strategy and what a run records are allowed to differ, and that
    mapping is pinned here so a nicer label can never quietly become the value a
    variant workflow is selected by.
    """

    def test_the_strategy_cards_map_onto_the_canonical_strategy_ids(self) -> None:
        for field in ("semantic_test_strategy", "transformation_strategy"):
            with self.subTest(field=field):
                self.assertEqual(
                    sorted(STRATEGY_LABELS), sorted(_field_options(field))
                )

    def test_a_selected_strategy_card_records_its_canonical_id(self) -> None:
        for label, expected in STRATEGY_LABELS.items():
            with self.subTest(label=label):
                config = _configure(
                    semantic_test_strategy=label, transformation_strategy=label
                )
                self.assertTrue(config["ok"], config.get("error"))
                llms = config["result"]["config"]["llms"]
                self.assertEqual(expected, llms["semantic_test"]["strategy"])
                self.assertEqual(expected, llms["transformation"]["strategy"])
                # The variant workflow is selected by that id, not by the label.
                spec = config["result"]["run_specs"][0]
                self.assertTrue(
                    spec["test_generation_workflow"].endswith(f"_{expected}.json"), spec
                )

    def test_an_unknown_strategy_label_is_refused(self) -> None:
        config = _configure(semantic_test_strategy="few_shot")
        self.assertFalse(config["ok"])
        self.assertIn("Semantic Test Generation strategy", config["error"])

    def test_each_refinement_budget_offers_the_evaluation_range(self) -> None:
        for field in (
            "max_test_refinement_iterations",
            "max_transformation_refinement_iterations",
        ):
            with self.subTest(field=field):
                self.assertEqual(["0", "1", "2", "3"], _field_options(field))

    def test_the_choice_fields_are_native_option_inputs(self) -> None:
        """Cards are CSS over radio/checkbox, not custom HTML controls.

        n8n forms only submit native inputs; an HTML element rendered as a button
        would show up and return nothing usable, so every field a run reads has to
        stay a real option input.
        """
        submitted_types = {"radio", "checkbox", "dropdown", "hiddenField"}
        for field in _form_fields():
            if field["fieldType"] == "html":
                continue
            with self.subTest(field=field.get("fieldName")):
                self.assertIn(field["fieldType"], submitted_types)

    def test_the_whole_configuration_is_one_screen(self) -> None:
        """One form node, so the run is configured behind a single link."""
        form_nodes = [
            node
            for node in _master()["nodes"]
            if node["type"] in ("n8n-nodes-base.form", "n8n-nodes-base.formTrigger")
        ]
        self.assertEqual(
            ["n8n-nodes-base.formTrigger"], [node["type"] for node in form_nodes]
        )
        css = form_nodes[0]["parameters"]["options"]["customCss"]
        self.assertIn(".multiselect-option", css)
        self.assertNotIn("<", css)

    def test_the_form_submits_the_names_the_queue_builder_reads(self) -> None:
        """The submitted key has to be the field name, not the field label.

        n8n's ``getFieldIdentifier`` only returns ``fieldName`` from typeVersion
        2.4 on. On 2.3 the same form posts ``{"Run mode": "Full Pipeline"}``, the
        queue builder reads ``form.run_mode``, and the run dies on the first
        validation with every field undefined.
        """
        version = _trigger_type_version()
        self.assertGreaterEqual(
            version, 2.4, "below 2.4 n8n keys the submitted item by fieldLabel"
        )
        for field in _form_fields():
            if field["fieldType"] == "html":
                continue
            with self.subTest(field=field.get("fieldName")):
                self.assertEqual(
                    field["fieldName"], _submitted_key(field, version)
                )

    def test_the_form_feeds_the_run_queue_directly(self) -> None:
        connections = _master()["connections"]
        self.assertEqual(
            "Validate Config and Build Run Queue",
            connections["Configure and Start Pipeline"]["main"][0][0]["node"],
        )

    def test_the_screen_collects_every_field_the_run_queue_reads(self) -> None:
        submitted = {
            field["fieldName"]
            for field in _form_fields()
            if field["fieldType"] != "html"
        }
        self.assertEqual(
            {
                "run_mode",
                "languages",
                "etl_tasks",
                "atl_tasks",
                "qvto_tasks",
                "reactions_tasks",
                "semantic_test_provider",
                "transformation_provider",
                "source_diagnosis_provider",
                "refinement_provider",
                "semantic_test_strategy",
                "transformation_strategy",
                "max_test_refinement_iterations",
                "max_transformation_refinement_iterations",
                "ablation_profile",
                "disabled_components",
                "n8n_workflow_root",
            },
            submitted,
        )


if __name__ == "__main__":
    unittest.main()
