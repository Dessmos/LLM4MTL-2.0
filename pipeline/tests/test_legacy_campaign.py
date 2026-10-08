from __future__ import annotations

import sys
import unittest
from pathlib import Path

from llm4mtl.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT))

from evaluation.legacy_campaign.execution import prepare_reactions
from evaluation.legacy_campaign.protocol import behavioral_outcome, minimal_context, qualified
from evaluation.legacy_campaign.report import listener_runtime_evidence, matched_class, paired_metrics
from evaluation.legacy_pilot.assessment import task_mapping
from evaluation.legacy_pilot.run_pilot import source_blocks


class LegacyCampaignMetricTests(unittest.TestCase):
    def rows(self, outcomes: list[str], strength: str = "behavioral") -> list[dict]:
        return [{"method": str(index), "strength": strength, "observed": outcome != "UNAVAILABLE", "outcome": outcome}
                for index, outcome in enumerate(outcomes)]

    def test_technical_failure_prevents_assertion_kill(self) -> None:
        for status in ("COMPILATION_ERROR", "RUNTIME_ERROR", "INFRASTRUCTURE_ERROR", "UNAVAILABLE"):
            with self.subTest(status=status):
                self.assertEqual(status, behavioral_outcome(self.rows(["ASSERTION_FAILURE", status])))

    def test_weak_method_does_not_gate_behavioral_qualification(self) -> None:
        rows = self.rows(["PASS"]) + self.rows(["RUNTIME_ERROR"], "source_only_weak")
        self.assertTrue(qualified(rows))
        self.assertEqual("PASS", behavioral_outcome(rows))

    def test_dependency_control_must_execute_and_change_behavior(self) -> None:
        self.assertTrue(qualified(self.rows(["PASS"]), self.rows(["ASSERTION_FAILURE"])))
        self.assertTrue(qualified(self.rows(["PASS"]), self.rows(["RUNTIME_ERROR"])))
        for status in ("PASS", "COMPILATION_ERROR", "INFRASTRUCTURE_ERROR", "UNAVAILABLE"):
            with self.subTest(status=status):
                self.assertFalse(qualified(self.rows(["PASS"]), self.rows([status])))

    def test_unobserved_pass_does_not_qualify(self) -> None:
        rows = self.rows(["PASS"])
        rows[0]["observed"] = False
        self.assertFalse(qualified(rows))


class LegacyCampaignContextTests(unittest.TestCase):
    def test_negative_control_removes_only_reaction_and_preserves_called_routines(self) -> None:
        context = "reactions: fixed\nreaction Target { call shared() }\nroutine shared() { update {} }\nreaction Background { call shared() }\n"
        reference = "reaction Target { call shared() }\nroutine shared() { update {} }\n"
        actual, facts = prepare_reactions(context, reference, reference, True)
        self.assertEqual(["shared", "Background"], [block.name for block in source_blocks(actual)])
        self.assertTrue(facts["background_unchanged"])

    def test_all_twelve_contexts_preserve_exact_original_blocks_and_target(self) -> None:
        for task in task_mapping():
            if task.language != "reactions":
                continue
            with self.subTest(task=task.task):
                actual, facts = minimal_context(task)
                original = {(block.kind, block.name): block.text for block in source_blocks(task.context_file.read_text(encoding="utf-8"))}
                self.assertEqual(set(facts["retained_declarations"]), {f"{block.kind}:{block.name}" for block in source_blocks(actual)})
                for block in source_blocks(actual):
                    self.assertEqual(original[(block.kind, block.name)], block.text)

    def test_deleted_member_stimulus_needs_created_father_not_daughter(self) -> None:
        task = next(task for task in task_mapping() if task.task == "FamiliesToPersons_DeletedMember")
        _, facts = minimal_context(task)
        self.assertIn("FamiliesToPersons_CreatedFather", facts["prerequisite_tasks"])
        self.assertNotIn("FamiliesToPersons_InsertedDaughter", facts["prerequisite_tasks"])


class LegacyCampaignReportingTests(unittest.TestCase):
    def test_listener_recovery_requires_exact_failed_method_and_runtime_exception(self) -> None:
        line = "WARNING: TestExecutionListener [RunListenerAdapter] executionFinished(TestIdentifier [uniqueId = [engine:junit-jupiter]/[class:org.example.SampleTest]/[method:testBehavior()], tags = []], TestExecutionResult [status = FAILED, throwable = org.eclipse.m2m.atl.engine.emfvm.VMException: invalid feature])"
        self.assertTrue(listener_runtime_evidence(line, "SampleTest", "testBehavior"))
        self.assertFalse(listener_runtime_evidence(line, "OtherTest", "testBehavior"))
        self.assertFalse(listener_runtime_evidence(line, "SampleTest", "otherMethod"))
        self.assertFalse(listener_runtime_evidence(line.replace("FAILED", "SUCCESSFUL"), "SampleTest", "testBehavior"))
        self.assertFalse(listener_runtime_evidence(line.replace("org.eclipse.m2m.atl.engine.emfvm.VMException", "org.opentest4j.AssertionFailedError"), "SampleTest", "testBehavior"))

    def test_unique_matching_uses_union_and_preserves_uninterpretable_manual_errors(self) -> None:
        generated = [{"reference_result": "PASS", "generated_outcome": status} for status in ("SURVIVED", "KILLED")]
        self.assertEqual(("BOTH", ""), matched_class("KILLED", generated))
        self.assertEqual(("GENERATED_ONLY", ""), matched_class("SURVIVED", generated))
        self.assertEqual(("MANUAL_ONLY", ""), matched_class("KILLED", generated[:1]))
        self.assertEqual(("NEITHER", ""), matched_class("SURVIVED", generated[:1]))
        self.assertEqual("UNINTERPRETABLE", matched_class("RUNTIME_ERROR", generated)[0])
        self.assertEqual("UNMATCHED", matched_class("SURVIVED", [{"reference_result": "FAIL", "generated_outcome": "KILLED"}])[0])

    def test_hand_calculated_pair_denominators_keep_technical_and_unavailable_slots(self) -> None:
        def method(status: str) -> dict:
            return {"method": "behavior", "strength": "behavioral", "observed": status != "UNAVAILABLE", "outcome": status}

        rows = [{"run_id": str(index), "qualified": a != "UNAVAILABLE", "Tpre_outcome": a, "Tpost_outcome": b,
                 "Tpre_methods": [method(a)], "Tpost_methods": [method(b)]}
                for index, (a, b) in enumerate((("ASSERTION_FAILURE", "PASS"), ("RUNTIME_ERROR", "PASS"),
                    ("PASS", "COMPILATION_ERROR"), ("UNAVAILABLE", "UNAVAILABLE")))]
        actual = paired_metrics(rows)
        self.assertEqual(4, actual["runs"])
        self.assertEqual(3, actual["qualified_runs"])
        self.assertEqual(4, actual["Tpost_behavioral_methods"])
        self.assertEqual(2, actual["suite_improvements"])
        self.assertEqual(2, actual["initially_nonpassing_qualified"])
        self.assertEqual(1, actual["assertion_only_repairs"])
        self.assertEqual(1, actual["technical_recoveries"])
        self.assertEqual(1, actual["suite_regressions"])
        self.assertEqual(1, actual["technical_losses"])
