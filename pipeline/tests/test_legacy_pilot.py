from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from llm4mtl.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from evaluation._common import SelectedRun
from evaluation.legacy_pilot.assessment import endpoints
from evaluation.legacy_pilot.run_pilot import (
    classify_build, classify_failure, compose_reactions, semantic_kill, source_blocks,
)


class LegacyPilotEndpointTests(unittest.TestCase):
    def test_semantic_pair_starts_after_syntax_repairs_and_includes_final_syntax_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = {"run_id": "sample", "language": "etl", "task": "sample"}
            for iteration in range(4):
                folder = root / "transformation" / f"iteration-{iteration:03d}"
                folder.mkdir(parents=True)
                path = folder / "sample.etl"
                path.write_text(f"// version {iteration}\n", encoding="utf-8")
                metadata = dict(manifest, iteration=iteration, transformations=[{
                    "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}])
                (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            generation = root / "generations/transformation/iteration-002"
            generation.mkdir(parents=True)
            (generation / "generation.json").write_text(json.dumps({"iteration": 2,
                "purpose": "semantic_refinement", "input_artifact_iteration": 1}), encoding="utf-8")
            initial_generation = root / "generations/transformation/iteration-000"
            initial_generation.mkdir(parents=True)
            (initial_generation / "generation.json").write_text(json.dumps({"purpose": "initial",
                "output_artifact": {"sha256": hashlib.sha256((root / "transformation/iteration-000/sample.etl").read_bytes()).hexdigest()}}), encoding="utf-8")
            request = root / "refinements/transformation/iteration-002"
            request.mkdir(parents=True)
            (request / "request.json").write_text(json.dumps({"previous_iteration": 1,
                "feedback": {"source": "semantic"},
                "previous_artifact": {"files": [{"content": "// version 1\n"}]}}), encoding="utf-8")
            actual = endpoints(SelectedRun("sample", root, manifest, {}))
            self.assertEqual((0, 1, 3), (actual.initial[0], actual.pre[0], actual.post[0]))


class LegacyPilotCompositionTests(unittest.TestCase):
    CONTEXT = '''import "a" as a
reactions: fixed
in reaction to changes in a
execute actions in a
reaction Background { call setup() }
routine setup() { update { val label = "}" /* { */ } }
reaction Target { call old() }
routine old() { update { /* old target body */ } }
'''
    REFERENCE = '''import "a" as a
reactions: target
in reaction to changes in a
execute actions in a
reaction Target { call old() }
routine old() { update { /* old target body */ } }
'''

    def test_replaces_only_target_blocks_and_preserves_fixed_background(self) -> None:
        candidate = self.REFERENCE.replace("old()", "replacement()")
        prepared, facts = compose_reactions(self.CONTEXT, self.REFERENCE, candidate)
        self.assertIn("reactions: fixed", prepared)
        self.assertIn('val label = "}" /* { */', prepared)
        self.assertNotIn("routine old()", prepared)
        self.assertIn("routine replacement()", prepared)
        self.assertTrue(facts["background_unchanged"])

    def test_absent_candidate_control_contains_no_target_reaction(self) -> None:
        prepared, facts = compose_reactions(self.CONTEXT, self.REFERENCE, None)
        self.assertEqual(["Background", "setup"], [block.name for block in source_blocks(prepared)])
        self.assertEqual([], facts["candidate_declarations"])

    def test_removing_target_between_background_blocks_does_not_compare_blank_lines(self) -> None:
        context = self.CONTEXT + "\nreaction Following { call setup() }\n"
        prepared, facts = compose_reactions(context, self.REFERENCE, self.REFERENCE)
        self.assertIn("reaction Following { call setup() }", prepared)
        self.assertTrue(facts["background_unchanged"])

    def test_rejects_candidate_that_overwrites_background_routine(self) -> None:
        with self.assertRaisesRegex(ValueError, "collides"):
            compose_reactions(self.CONTEXT, self.REFERENCE, self.REFERENCE.replace("old()", "setup()"))


class LegacyPilotOutcomeTests(unittest.TestCase):
    def test_qvto_execution_diagnostic_assertion_is_not_a_semantic_failure(self) -> None:
        outcome = classify_failure("failure", "org.opentest4j.AssertionFailedError",
            "Transformation failed: execution error", "QvtoTestBase.executeTransformation(QvtoTestBase.java:75)")
        self.assertEqual("RUNTIME_ERROR", outcome)

    def test_xtext_validation_failure_is_compilation_not_infrastructure(self) -> None:
        self.assertEqual("COMPILATION_ERROR", classify_build(
            "Failed to execute goal xtext-maven-plugin:generate: severe validation error"))

    def test_offline_missing_dependency_is_infrastructure(self) -> None:
        self.assertEqual("INFRASTRUCTURE_ERROR", classify_build("Could not resolve dependency in offline mode"))

    def test_only_reference_passing_behavioral_assertion_kills(self) -> None:
        reference = [{"method": "behavior", "strength": "behavioral", "outcome": "PASS", "observed": True}]
        mutant = [dict(reference[0], outcome="ASSERTION_FAILURE")]
        self.assertTrue(semantic_kill(reference, mutant))
        for outcome, strength, observed in [("RUNTIME_ERROR", "behavioral", True),
            ("COMPILATION_ERROR", "behavioral", False), ("ASSERTION_FAILURE", "resource_smoke", True),
            ("ASSERTION_FAILURE", "source_only_weak", True)]:
            with self.subTest(outcome=outcome, strength=strength):
                self.assertFalse(semantic_kill(reference, [dict(mutant[0], outcome=outcome,
                                                               strength=strength, observed=observed)]))
        self.assertFalse(semantic_kill([dict(reference[0], outcome="ASSERTION_FAILURE")], mutant))
