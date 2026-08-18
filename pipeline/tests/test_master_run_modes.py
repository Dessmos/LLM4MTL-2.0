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

# What each provider's standard AI Model node looks like once a model is picked
# in its built-in selector. Google keeps the model under a different parameter.
PROVIDER_PARAMS = {
    "OpenAI": {"model": {"value": "gpt-5-2025-08-07"}},
    "Anthropic": {"model": {"value": "claude-sonnet-4-20250514"}},
    "Google Gemini": {"modelName": "models/gemini-2.5-pro"},
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


def _form_fields(node_name: str) -> list[dict[str, Any]]:
    node = next(node for node in _master()["nodes"] if node["name"] == node_name)
    return node["parameters"]["formFields"]["values"]


def _field_options(node_name: str, field_name: str) -> list[str]:
    field = next(
        field
        for field in _form_fields(node_name)
        if field.get("fieldName") == field_name
    )
    return [option["option"] for option in field["fieldOptions"]["values"]]


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
    semantic_test_strategy: str = "few_shot",
    transformation_strategy: str = "grammar",
    max_refinement_iterations: str = "2",
    ablation_profile: str = "Standard full configuration",
    disabled_components: str = "",
    unconfigured_roles: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Submit the four configuration screens and build the run queue."""
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
        nodes={
            "Configure and Start Pipeline": {
                "json": {
                    "run_mode": run_mode,
                    "languages": languages,
                    **chosen,
                    **provider_choice,
                    "n8n_workflow_root": "/data/repository/workflows/n8n",
                }
            },
            "Semantic Test Configuration": {
                "json": {"semantic_test_strategy": semantic_test_strategy}
            },
            "Transformation Configuration": {
                "json": {"transformation_strategy": transformation_strategy}
            },
            "Experiment and Ablation": {
                "json": {
                    "max_refinement_iterations": max_refinement_iterations,
                    "ablation_profile": ablation_profile,
                    "disabled_components": disabled_components,
                }
            },
            **_model_nodes(unconfigured_roles),
        },
    )


# What each stage reports back when everything succeeds.
PASSING_RESULTS = {
    "create_run": {"run_id": "etl-tree2graph-0001"},
    "generate_tests": {"status": "completed"},
    "extract": {"stage": "extract", "status": "completed", "outcome_code": "EXTRACTED"},
    "technical": {"stage": "technical-validation", "status": "completed", "outcome_code": "TECH_VALID"},
    "reference": {"stage": "reference-validation", "status": "completed", "outcome_code": "REFERENCE_VALIDATED"},
    "generate_transformations": {"status": "completed"},
    "syntax": {"stage": "syntax-validation", "status": "completed", "outcome_code": "SYNTAX_VALID"},
    "execution": {"stage": "execution", "status": "completed", "outcome_code": "SEMANTIC_PASSED"},
    "final": {"artifacts": {}},
}


def _drive(
    config: dict[str, Any],
    results: dict[str, Any] | None = None,
    limit: int = 60,
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
        action = state["action"]
        actions.append(action)
        if action == "complete":
            return actions, state
        captured = _run_node(
            "Capture Action Result",
            inputs=[stage_results.get(action, {})],
            nodes={"State Machine": {"json": state}},
        )
        if not captured["ok"]:
            raise AssertionError(captured["error"])
        state = captured["result"]
    raise AssertionError(f"control loop did not terminate: {actions}")


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class RunModeTests(unittest.TestCase):
    def test_tests_only_never_routes_into_transformation_generation(self) -> None:
        config = _configure(run_mode="Semantic Tests Only")
        self.assertTrue(config["ok"], config.get("error"))
        actions, state = _drive(config["result"])
        for action in ("generate_transformations", "syntax", "execution", "diagnose"):
            self.assertNotIn(action, actions)
        self.assertEqual(
            ["create_run", "generate_tests", "extract", "technical", "reference", "final", "complete"],
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
            ["create_run", "generate_transformations", "syntax", "final", "complete"],
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
                "extract",
                "technical",
                "reference",
                "generate_transformations",
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
        config = _configure(run_mode="Full Pipeline")
        actions, _ = _drive(
            config["result"],
            results={
                "execution": {
                    "stage": "execution",
                    "status": "completed",
                    "outcome_code": "SEMANTIC_EXECUTION_FAILED",
                    "artifacts": {"failure_report_path": "/data/artifacts/failure.json"},
                },
                "diagnose": {"classification": "transformation_defect", "confidence": "high"},
            },
        )
        self.assertIn("diagnose", actions)
        # The diagnosed transformation defect sends the run back through
        # transformation generation rather than test generation.
        self.assertEqual("generate_transformations", actions[actions.index("diagnose") + 1])

    def test_every_run_mode_has_a_successful_terminal_path(self) -> None:
        for mode in ("Semantic Tests Only", "Transformations Only", "Full Pipeline"):
            with self.subTest(mode=mode):
                config = _configure(run_mode=mode)
                self.assertTrue(config["ok"], config.get("error"))
                _, state = _drive(config["result"])
                self.assertEqual("completed", state["results"][0]["status"])


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
                self.assertEqual(
                    contracts,
                    sorted(
                        _field_options("Configure and Start Pipeline", f"{language}_tasks")
                    ),
                )


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

    def test_zero_refinement_iterations_removes_the_refinement_requirement(self) -> None:
        config = _configure(
            max_refinement_iterations="0", unconfigured_roles=("refinement",)
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
        self.assertEqual(
            "Semantic Test Generation - Google Gemini Chat Model",
            semantic_test["configuration_node"],
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
            sorted(STAGE_FIELDS),
            sorted(_field_options("Experiment and Ablation", "disabled_components")),
        )

    def test_run_mode_and_stage_flags_stay_separate_in_the_config(self) -> None:
        config = _configure(run_mode="Semantic Tests Only")["result"]["config"]
        # The mode narrows what executes; it does not pretend the transformation
        # components were ablated.
        self.assertEqual("tests_only", config["run_mode"])
        self.assertTrue(config["stages"]["transformation_generation"])
        self.assertTrue(config["stages"]["syntax_validation"])


if __name__ == "__main__":
    unittest.main()
