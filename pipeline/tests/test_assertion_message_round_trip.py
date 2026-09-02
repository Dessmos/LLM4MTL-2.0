"""The failure message the harness prints is the one diagnosis looks for.

An assertion's message is written once, into generated Java, and read back
once, out of a Surefire report, to work out which assertion lost. Nothing fails
when the two disagree: the renderer still emits a valid harness and the report
still records a real failure, but no assertion matches it, so the failure is
refused instead of diagnosed.

The rule therefore has one owner, ``java_rendering.assertion_message``. These
tests state the expected message for each case as a literal rather than
deriving it from that function — a test that asked the rule what the rule says
would pass no matter what the rule became. Each expectation is then checked
against both directions: the Java the renderer emits, and the assertion
diagnosis attributes a recorded failure to.
"""

from __future__ import annotations

import re
import unittest

from llm4mtl.languages.java_assertions import render_assertions
from llm4mtl.semantic_tests.codegen.java import render_assertion
from llm4mtl.semantic_tests.codegen.java_rendering import (
    assertion_message,
    escape_java,
)
from llm4mtl.semantic_tests.diagnosis_preparation import _match_assertion
from llm4mtl.semantic_tests.failure_report import FailureReportError
from llm4mtl.semantic_tests.failure_report.case_report import _assertion_message

MODEL_VARIABLES = {"OUT": "model0"}
# Two harness emitters are live: ETL renders through codegen.java, the other
# three languages through languages.java_assertions. Both must print the one
# message, or a diagnosis works for some languages and not others.
EMITTERS = {
    "codegen.java": lambda assertion: render_assertion(assertion, MODEL_VARIABLES),
    "languages.java_assertions": lambda assertion: render_assertions(
        [assertion], MODEL_VARIABLES
    ),
}
# The message is the last string literal on a rendered assertion line.
EMITTED_MESSAGE = re.compile(r'"((?:[^"\\]|\\.)*)"\);\s*$')

NODE = {"kind": "count", "model": "OUT", "type": "Node", "expected": 2}

# name -> (assertion, the exact message the harness prints when it fails)
CASES = {
    "default text": (NODE, "count assertion for OUT::Node"),
    "own message": (
        {**NODE, "message": "the graph must keep one node per tree node"},
        "the graph must keep one node per tree node",
    ),
    "message needing Java escaping": (
        {**NODE, "message": 'expected "one" back\\slash'},
        'expected "one" back\\slash',
    ),
    "empty message falls back": (
        {**NODE, "message": ""},
        "count assertion for OUT::Node",
    ),
    # semantic_cases.schema.json does not constrain `message`, so a model can
    # emit a non-string one. The renderer stringifies it, so the reader has to
    # stringify it the same way or never match the failure it caused.
    "non-string message": ({**NODE, "message": 404}, "404"),
    "collection assertion": (
        {
            "kind": "featureValues",
            "model": "OUT",
            "type": "Node",
            "feature": "name",
            "expected": ["first", "second"],
        },
        "featureValues assertion for OUT::Node",
    ),
    "size assertion": (
        {
            "kind": "collectionSize",
            "model": "OUT",
            "type": "Node",
            "where": {"name": "root"},
            "path": "children",
            "expected": 1,
        },
        "collectionSize assertion for OUT::Node",
    ),
}


def emitted_literal(emitter, assertion: dict[str, object]) -> str:
    """The message literal an emitter actually embedded in the harness."""
    line = emitter(assertion)[-1]
    match = EMITTED_MESSAGE.search(line)
    assert match is not None, line
    return match.group(1)


class AssertionMessageTests(unittest.TestCase):

    def test_the_rule_produces_the_expected_message(self) -> None:
        for name, (assertion, expected) in CASES.items():
            with self.subTest(assertion=name):
                self.assertEqual(expected, assertion_message(assertion))

    def test_every_harness_emitter_prints_that_message(self) -> None:
        """Each emitter embeds it, escaped only as a Java literal requires."""
        for emitter_name, emitter in EMITTERS.items():
            for name, (assertion, expected) in CASES.items():
                with self.subTest(emitter=emitter_name, assertion=name):
                    self.assertEqual(
                        escape_java(expected),
                        emitted_literal(emitter, assertion),
                    )

    def test_the_report_looks_for_that_message(self) -> None:
        """The failure report proves its assertion against the printed message."""
        for name, (assertion, expected) in CASES.items():
            with self.subTest(assertion=name):
                self.assertEqual(expected, _assertion_message(assertion))

    def test_diagnosis_attributes_a_failure_that_printed_that_message(self) -> None:
        """The recorded message carries JUnit's own detail, so it matches as a prefix."""
        for name, (assertion, expected) in CASES.items():
            with self.subTest(assertion=name):
                semantic_cases = {
                    "tests": [
                        {
                            "id": "case-1",
                            "assertions": [{**assertion, "id": "assertion-042"}],
                        }
                    ]
                }
                self.assertEqual(
                    "assertion-042",
                    _match_assertion(
                        semantic_cases,
                        "case-1",
                        f"{expected} ==> expected: <2> but was: <1>",
                    ),
                )

    def test_an_assertion_with_nothing_to_name_it_is_refused_not_guessed(
        self,
    ) -> None:
        """An empty message must never match; it would attribute the failure blindly."""
        unnameable = {"expected": 1}
        self.assertEqual("", assertion_message(unnameable))
        semantic_cases = {"tests": [{"id": "case-1", "assertions": [unnameable]}]}
        with self.assertRaises(FailureReportError):
            _match_assertion(semantic_cases, "case-1", "anything at all")
        # The report refuses it outright rather than returning a blank message
        # that would match every recorded failure by substring.
        with self.assertRaises(FailureReportError):
            _assertion_message(unnameable)


if __name__ == "__main__":
    unittest.main()
