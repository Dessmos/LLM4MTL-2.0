from __future__ import annotations

import sys
import unittest

from llm4mtl.paths import REPO_ROOT


sys.path.insert(0, str(REPO_ROOT))

from evaluation.failure_analysis import (
    RQ3_FAILED_AFTER_REFINEMENT,
    RQ3_FAILED_NOT_REFINED,
    RQ3_RECOVERED,
    classify_execution_failure,
    classify_parser_messages,
    diagnosis_outcome,
    execution_fingerprint,
    parser_messages,
    regressed_cases,
    semantic_outcome_reason,
    semantic_population,
)
from evaluation.rq_metrics import Execution, Refinement, RunFacts


def _run(executions: list[Execution], refinements: list[Refinement], final_iteration: int) -> RunFacts:
    return RunFacts(
        group="g", model="m", run_id="r", language="atl", suites=(), syntax=(),
        refinements=tuple(refinements), executions=tuple(executions),
        final_transformation_iteration=final_iteration, diagnoses=(), mutant_row=None,
        test_refinement_budget=3, transformation_refinement_budget=3,
    )


def _execution(attempt: int, transformation: int, cases: dict[str, str] | None, suite: int = 0) -> Execution:
    is_passed = cases is not None and all(outcome == "PASS" for outcome in cases.values())
    return Execution(attempt, transformation, suite, is_passed, cases)


def _semantic(iteration: int, artifact_type: str = "transformation") -> Refinement:
    return Refinement(artifact_type, "semantic_refinement", iteration, False, iteration)


def _syntax(iteration: int) -> Refinement:
    return Refinement("transformation", "syntax_refinement", iteration, False, None)


class ExecutionFailureClassTests(unittest.TestCase):

    def test_recorded_messages_map_to_their_class(self) -> None:
        cases = [
            ("model_loading", "t: Cannot find reference model amalthea", "MODEL_BINDING_MISMATCH"),
            ("unclassified_runtime", "t: Type 'flowchart!Flowchart' not found", "MODEL_BINDING_MISMATCH"),
            ("model_loading", "t: org.eclipse.emf.ecore.xmi.ClassNotFoundException: Class 'Type'",
             "MODEL_NONCONFORMANT"),
            ("unclassified_runtime", "t: Unable to access name on OclUndefined", "RUNTIME_UNDEFINED_NAVIGATION"),
            ("engine_runtime", "t: Operation not found: OclUndefined.not()", "RUNTIME_UNDEFINED_NAVIGATION"),
            ("engine_runtime", "t: Operation not found: IN!<unnamed>.oclAsType(x)", "RUNTIME_OPERATION_NOT_FOUND"),
            ("unclassified_runtime", "t: Undefined variable, type or model: 'TM!TypeMap'",
             "RUNTIME_UNRESOLVED_NAME_OR_TYPE"),
            ("assertion_failure", "t(Path): count assertion for persons::Female ==> expected: <0> but was: <1>",
             "ASSERTION_COUNT"),
            ("assertion_failure", "t: featureValues assertion for OUT::A ==> expected", "ASSERTION_FEATURE_VALUES"),
            ("unclassified_runtime", "t(Path): No X11 DISPLAY variable was set", "ENVIRONMENT_GUI_INTERACTION"),
            ("engine_runtime", "t(Path): Cannot identify the packages of this change: x", "REACTIONS_EMPTY_CHANGE"),
            ("transformation_parse", "t: Transformation failed", "TRANSFORMATION_COMPILE_ERROR"),
            ("engine_runtime", "t: java.lang.StackOverflowError", "ENGINE_CRASH"),
            ("unclassified_runtime", "t: something nobody anticipated", "OTHER_RUNTIME"),
        ]
        for failure_stage, summary, expected in cases:
            with self.subTest(summary=summary):
                self.assertEqual(classify_execution_failure(failure_stage, summary), expected)

    def test_assertion_fingerprint_keeps_kind_and_metaclass_only(self) -> None:
        self.assertEqual(
            execution_fingerprint("deletingTask(Path): count assertion for ascet::InterruptTask ==> expected: <0>"),
            "count assertion for ascet::InterruptTask",
        )

    def test_runtime_fingerprint_drops_test_name_and_object_identity(self) -> None:
        self.assertEqual(
            execution_fingerprint("singleClass: Property 'name' not found in object Impl@675d8c96 (eClass)"),
            "Property 'name' not found in object Impl (eClass)",
        )


class ParserFailureTests(unittest.TestCase):

    def test_atl_keyword_used_as_variable_name(self) -> None:
        diagnostics = ("RESULT:FAIL:1\n\nFAIL: /app/x/T.atl (1 errors)\n  - Problem@1f08d5eb (severity: error, "
                       "location: 65:18, description: mismatched input 'in' expecting NAME)")
        messages = parser_messages(diagnostics)

        self.assertEqual(messages, ("mismatched input 'in' expecting NAME",))
        self.assertEqual(classify_parser_messages("atl", messages).category, "KEYWORD_AS_IDENTIFIER")

    def test_etl_rule_extends_before_transform(self) -> None:
        messages = parser_messages("ERROR line 9:1 mismatched input 'extends' expecting 'transform'")

        self.assertEqual(classify_parser_messages("etl", messages).category, "RULE_DECLARATION_SYNTAX")

    def test_reactions_grammar_error_wins_over_its_linking_cascade(self) -> None:
        messages = parser_messages(
            "Syntax issues (3): missing 'retrieve' at 'm' (ERROR) persons cannot be resolved to a type. (ERROR) "
            "The method or field name is undefined (ERROR)")
        failure = classify_parser_messages("reactions", messages)

        self.assertEqual(len(messages), 3)
        self.assertEqual(failure.category, "REACTIONS_BLOCK_GRAMMAR")
        self.assertEqual(failure.error_kinds, "grammar+linking")

    def test_first_specific_message_names_the_category(self) -> None:
        messages = ("missing 'else' at 'elseif'", "mismatched input 'in' expecting NAME")

        self.assertEqual(classify_parser_messages("atl", messages).category, "CONTROL_FLOW_SYNTAX")

    def test_reactions_linking_errors_alone_are_unresolved_references(self) -> None:
        messages = parser_messages("Syntax issues (1): ascet cannot be resolved to a type. (ERROR)")

        self.assertEqual(classify_parser_messages("reactions", messages).category, "UNRESOLVED_REFERENCE")

    def test_reactions_inferrer_exception_is_a_parser_crash(self) -> None:
        messages = parser_messages(
            "0 [main] ERROR t.xbase.jvmmodel.JvmModelAssociator  - Error calling inferrer "
            "java.lang.IllegalArgumentException: reaction must have a defined trigger \tat com.google")

        self.assertEqual(messages, ("java.lang.IllegalArgumentException: reaction must have a defined trigger",))
        self.assertEqual(classify_parser_messages("reactions", messages).category, "PARSER_CRASH")


class SemanticOutcomeTests(unittest.TestCase):

    def test_same_failing_cases_after_spent_budget(self) -> None:
        failing = {"A": "FAIL", "B": "PASS"}
        run = _run([_execution(1, 0, failing), _execution(2, 1, failing)], [_semantic(1)], final_iteration=1)

        self.assertEqual(semantic_population(run), RQ3_FAILED_AFTER_REFINEMENT)
        self.assertEqual(
            semantic_outcome_reason(run, "DIAGNOSED_TRANSFORMATION_DEFECT:REFINEMENT_LIMIT_REACHED", {}),
            "BUDGET_EXHAUSTED_SAME_FAILURE",
        )

    def test_different_failing_cases_after_spent_budget(self) -> None:
        run = _run([_execution(1, 0, {"A": "FAIL", "B": "PASS"}), _execution(2, 1, {"A": "PASS", "B": "FAIL"})],
                   [_semantic(1)], final_iteration=1)

        self.assertEqual(
            semantic_outcome_reason(run, "DIAGNOSED_TRANSFORMATION_DEFECT:REFINEMENT_LIMIT_REACHED", {}),
            "BUDGET_EXHAUSTED_DIFFERENT_FAILURE",
        )

    def test_unexecuted_last_iteration_means_refinement_broke_syntax(self) -> None:
        run = _run([_execution(1, 0, {"A": "FAIL"})], [_semantic(1)], final_iteration=1)

        self.assertEqual(semantic_outcome_reason(run, "SYNTAX_INVALID:REFINEMENT_LIMIT_REACHED", {}),
                         "REFINEMENT_BROKE_SYNTAX")

    def test_ambiguous_diagnosis_stops_before_any_refinement(self) -> None:
        run = _run([_execution(1, 0, {"A": "FAIL"})], [], final_iteration=0)

        self.assertEqual(semantic_population(run), RQ3_FAILED_NOT_REFINED)
        self.assertEqual(semantic_outcome_reason(run, "AMBIGUOUS_SOURCE_DIAGNOSIS", {}),
                         "STOPPED_AMBIGUOUS_DIAGNOSIS")

    def test_syntax_refinements_can_spend_the_whole_budget(self) -> None:
        run = _run([_execution(1, 3, {"A": "FAIL"})], [_syntax(1), _syntax(2), _syntax(3)], final_iteration=3)

        self.assertEqual(
            semantic_outcome_reason(run, "DIAGNOSED_TRANSFORMATION_DEFECT:REFINEMENT_LIMIT_REACHED", {}),
            "BUDGET_SPENT_ON_SYNTAX",
        )

    def test_passing_tfinal_is_recovered_by_transformation_refinement(self) -> None:
        run = _run([_execution(1, 0, {"A": "FAIL"}), _execution(2, 1, {"A": "PASS"})], [_semantic(1)],
                   final_iteration=1)

        self.assertEqual(semantic_population(run), RQ3_RECOVERED)
        self.assertEqual(semantic_outcome_reason(run, "SEMANTIC_PASSED", {}),
                         "RECOVERED_BY_TRANSFORMATION_REFINEMENT")

    def test_regressed_cases_count_pass_to_fail_under_the_same_suite(self) -> None:
        run = _run([_execution(1, 0, {"A": "PASS", "B": "FAIL"}), _execution(2, 1, {"A": "FAIL", "B": "PASS"})],
                   [_semantic(1)], final_iteration=1)

        self.assertEqual(regressed_cases(run), 1)

    def test_diagnosis_outcome_lists_most_frequent_verdict_first(self) -> None:
        self.assertEqual(diagnosis_outcome(["TEST_DEFECT", "AMBIGUOUS", "TEST_DEFECT"]), "TEST_DEFECT+AMBIGUOUS")
        self.assertEqual(diagnosis_outcome([]), "")


if __name__ == "__main__":
    unittest.main()
