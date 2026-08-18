"""Which subworkflow the master actually executes.

The master workflow resolves a prompting strategy to a file through a glob whose
``*`` stands for the model token. Globs do not respect token boundaries: the
selector for ``grammar`` also reads every ``few_shots_AND_grammar`` variant back,
and an experiment that runs a different prompting strategy than the one recorded
in its configuration produces results attributed to a condition that never ran.
Selection is therefore a measured property, not an implementation detail.

The master workflow is authored in the n8n editor, so these tests execute its
shipped JavaScript under Node rather than restating the rules in Python.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_ROOT = REPOSITORY_ROOT / "workflows" / "n8n"
MASTER_WORKFLOW = WORKFLOWS_ROOT / "main" / "llm4mtl-agent-workflow.json"
CODE_NODE = "Make Existing Workflow Callable"
HARNESS = Path(__file__).parent / "fixtures" / "run_master_code_node.js"

STRATEGIES = ("only_prompt", "few_shot", "grammar", "few_shots_AND_grammar")
LANGUAGE_LABELS = {"etl": "ETL", "atl": "ATL", "qvto": "QVTO"}
# The model token a variant file is named after, per provider. Passing it as the
# selected model keeps the model-patching step a no-op so the assertions read
# the selection and nothing else.
PROVIDER_MODELS = {
    "openai": "gpt-5",
    "anthropic": "claude-sonnet-4",
    "google": "gemini-2-5-pro",
}


def _master_document() -> dict[str, Any]:
    return json.loads(MASTER_WORKFLOW.read_text(encoding="utf-8"))


def _node_code(name: str) -> str:
    node = next(node for node in _master_document()["nodes"] if node["name"] == name)
    return node["parameters"]["jsCode"]


def _selector_templates() -> dict[str, str]:
    """The two variant selectors the master builds, read from the master itself.

    Hard-coding the naming scheme here would let the test keep passing after the
    master stopped using it, which is the one failure a selection test may not
    have.
    """
    code = _node_code("Validate Config and Build Run Queue")
    templates = {}
    for kind, marker in (
        ("transformation", "/transformations/workflows/"),
        ("test_generation", "/tests/workflows/"),
    ):
        # `*` keeps this off the reactions branch, which names a single file.
        pattern = r"`\$\{root\}(" + re.escape(marker) + r"[^`]*\*[^`]*)`"
        match = re.search(pattern, code)
        assert match is not None, f"master builds no {kind} selector"
        templates[kind] = match.group(1)
    return templates


def _selector(kind: str, language: str, strategy: str) -> str:
    template = _selector_templates()[kind]
    strategy_expression = (
        "${llms.transformation.strategy}"
        if kind == "transformation"
        else "${llms.semantic_test.strategy}"
    )
    return (
        template.replace("${language}", language)
        .replace("${label}", LANGUAGE_LABELS[language])
        .replace(strategy_expression, strategy)
    )


def _glob_matches(selector: str) -> list[Path]:
    return sorted(WORKFLOWS_ROOT.glob(selector.lstrip("/")))


def _run_code_node(state: dict[str, Any], files: list[Path]) -> dict[str, Any]:
    spec = {
        "master": str(MASTER_WORKFLOW),
        "node": CODE_NODE,
        "state": state,
        "files": [str(path) for path in files],
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


@unittest.skipUnless(shutil.which("node"), "the master workflow's Code nodes need Node")
class MasterSubworkflowSelectionTests(unittest.TestCase):
    def test_each_language_provider_strategy_selects_exactly_one_workflow(self) -> None:
        checked = 0
        for kind, prefix in (
            ("transformation", "Prompting_{label}"),
            ("test_generation", "Prompting_tests_{label}"),
        ):
            for language, label in LANGUAGE_LABELS.items():
                for provider, model in PROVIDER_MODELS.items():
                    for strategy in STRATEGIES:
                        selector = _selector(kind, language, strategy)
                        matches = _glob_matches(selector)
                        expected_name = (
                            f"{prefix.format(label=label)}_{model}_{strategy}.json"
                        )
                        expected = next(
                            (path for path in matches if path.name == expected_name),
                            None,
                        )
                        with self.subTest(
                            kind=kind,
                            language=language,
                            provider=provider,
                            strategy=strategy,
                        ):
                            self.assertIsNotNone(
                                expected, f"no variant file named {expected_name}"
                            )
                            outcome = _run_code_node(
                                {
                                    "subworkflow_path": selector,
                                    "subworkflow_input": {
                                        "provider": provider,
                                        "model": model,
                                        "strategy": strategy,
                                    },
                                },
                                matches,
                            )
                            self.assertTrue(outcome["ok"], outcome.get("error"))
                            self.assertEqual(
                                json.loads(expected.read_text(encoding="utf-8"))["name"],
                                outcome["result"]["workflow_json"]["name"],
                            )
                            checked += 1
        self.assertEqual(
            len(LANGUAGE_LABELS) * len(PROVIDER_MODELS) * len(STRATEGIES) * 2, checked
        )

    def test_the_grammar_selector_still_reads_the_combined_strategy_back(self) -> None:
        """The glob is genuinely ambiguous, so exact selection is doing real work.

        If the variant files were ever renamed so that ``*_grammar.json`` stopped
        matching ``*_few_shots_AND_grammar.json``, the test above would keep
        passing for a reason that no longer holds. This records why it passes.
        """
        for kind in ("transformation", "test_generation"):
            for language in LANGUAGE_LABELS:
                with self.subTest(kind=kind, language=language):
                    names = {
                        path.name
                        for path in _glob_matches(_selector(kind, language, "grammar"))
                    }
                    self.assertTrue(
                        any(name.endswith("_few_shots_AND_grammar.json") for name in names),
                        names,
                    )

    def test_a_strategyless_selector_rejects_an_unknown_strategy(self) -> None:
        selector = _selector("transformation", "etl", "grammar")
        outcome = _run_code_node(
            {
                "subworkflow_path": selector,
                "subworkflow_input": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "strategy": "handwritten",
                },
            },
            _glob_matches(selector),
        )
        self.assertFalse(outcome["ok"])
        self.assertIn("requires a supported strategy", outcome["error"])

    def test_the_diagnosis_namespace_survives_model_patching(self) -> None:
        """``/responses/source-diagnosis/`` names a stage, not a model.

        The model patch rewrites ``/responses/<model>/`` so a variant workflow
        files its output under the model the master selected. The diagnosis
        subworkflow writes into the stage's own namespace instead; rewriting that
        to a model directory would attribute the stage's artifacts to a model that
        never produced them.
        """
        diagnosis = WORKFLOWS_ROOT / "subworkflows" / "diagnosis" / "llm-diagnosis.json"
        self.assertIn(
            "/responses/source-diagnosis/", diagnosis.read_text(encoding="utf-8")
        )
        outcome = _run_code_node(
            {
                "subworkflow_path": str(diagnosis),
                "subworkflow_input": {
                    "diagnosis_provider": "openai",
                    "model": "gpt-5-2025-08-07",
                },
            },
            [diagnosis],
        )
        self.assertTrue(outcome["ok"], outcome.get("error"))
        patched = json.dumps(outcome["result"]["workflow_json"])
        self.assertIn("/responses/source-diagnosis/", patched)
        self.assertNotIn("/responses/gpt-5-2025-08-07/", patched)


if __name__ == "__main__":
    unittest.main()
