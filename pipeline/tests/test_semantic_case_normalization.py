"""Normalization may rewrite how a specification is written, never what it says.

RQ1 measures whether LLM-generated tests are executable and pass reference
validation. A pipeline that repairs a malformed specification before that
measurement reports its own competence instead of the model's, so every repair
removed here is a measurement defect, not a convenience.

The prompt contract already promises this: a response that deviates from it "is
rejected before anything is executed and is recorded as an invalid artifact, not
as a failing test". These tests hold the implementation to that promise.
"""

from __future__ import annotations

import json
import unittest

from llm4mtl.conventions import ETL_CONFIG
from llm4mtl.domain import INVALID_SEMANTIC_CASES
from llm4mtl.semantic_tests.codegen.java import render_semantic_test
from llm4mtl.semantic_tests.extraction.semantic_cases import render_generated_suite
from llm4mtl.semantic_tests.extraction.semantic_cases.errors import SemanticCasesError
from llm4mtl.semantic_tests.extraction.semantic_cases.normalization import (
    normalize_metamodels,
)
from llm4mtl.semantic_tests.extraction.semantic_cases.parsing import parse_semantic_cases
from llm4mtl.semantic_tests.semantic_spec import SEMANTIC_CASES_FILE

SOURCE_MODEL = {
    "name": "Tree",
    "kind": "emf",
    "role": "source",
    "path": "models/input.model",
    "generated": True,
    "metamodelUri": "Tree",
}
TARGET_MODEL = {
    "name": "Graph",
    "kind": "emf",
    "role": "target",
    "generated": False,
    "metamodelUri": "Graph",
}
VALID_ASSERTION = {"kind": "count", "model": "Graph", "type": "Node", "expected": 2}


def spec_with(assertion: dict, *, models: list[dict] | None = None) -> str:
    return json.dumps(
        {
            "schemaVersion": 1,
            "transformation": "transformations/Tree2Graph.etl",
            "tests": [
                {
                    "name": "case",
                    "models": models
                    if models is not None
                    else [SOURCE_MODEL, TARGET_MODEL],
                    "assertions": [assertion],
                }
            ],
        }
    )


def parse(raw: str) -> dict:
    return parse_semantic_cases(raw, "Tree2Graph", transformation_extension=".etl")


class NoAssertionKindRewritingTests(unittest.TestCase):
    """One assertion kind must never be silently turned into another."""

    def test_path_values_carrying_paths_is_not_turned_into_tree_paths(self) -> None:
        with self.assertRaises(SemanticCasesError):
            parse(
                spec_with(
                    {
                        "kind": "pathValues",
                        "model": "Graph",
                        "type": "Node",
                        "paths": ["/a", "/a/b"],
                    }
                )
            )

    def test_feature_values_carrying_size_is_not_turned_into_collection_size(
        self,
    ) -> None:
        with self.assertRaises(SemanticCasesError):
            parse(
                spec_with(
                    {
                        "kind": "featureValues",
                        "model": "Graph",
                        "type": "Node",
                        "feature": "edges",
                        "size": 3,
                        "where": {"name": "root"},
                    }
                )
            )

    def test_reference_pairs_carrying_expected_targets_is_not_turned_into_path_values(
        self,
    ) -> None:
        with self.assertRaises(SemanticCasesError):
            parse(
                spec_with(
                    {
                        "kind": "referencePairs",
                        "model": "Graph",
                        "type": "Edge",
                        "sourceFeature": "source",
                        "expectedTargetObjects": [{"name": "b"}],
                    }
                )
            )


class NoExpectedScavengingTests(unittest.TestCase):
    """A missing `expected` is a defective specification, not a lookup problem.

    The contract states it outright: "Do not replace `expected` with `value`,
    `values`, `equals`, `ids`, `pairs`, `where`, or `match`."
    """

    def test_a_where_clause_is_not_used_as_the_expected_value(self) -> None:
        with self.assertRaises(SemanticCasesError):
            parse(
                spec_with(
                    {
                        "kind": "featureValues",
                        "model": "Graph",
                        "type": "Node",
                        "feature": "name",
                        "where": {"name": "root"},
                    }
                )
            )

    def test_no_alternate_primary_key_stands_in_for_expected(self) -> None:
        for alternate in (
            "equals",
            "values",
            "value",
            "equalsSet",
            "match",
            "ids",
            "pairs",
        ):
            with self.subTest(alternate=alternate):
                with self.assertRaises(SemanticCasesError):
                    parse(
                        spec_with(
                            {
                                "kind": "featureValues",
                                "model": "Graph",
                                "type": "Node",
                                "feature": "name",
                                alternate: ["a", "b"],
                            }
                        )
                    )


class NoInventedModelsTests(unittest.TestCase):

    def test_a_target_model_the_response_never_declared_is_not_created(self) -> None:
        raw = json.dumps(
            {
                "schemaVersion": 1,
                "transformation": "transformations/Tree2Graph.etl",
                "metamodels": [{"name": "Graph", "uri": "Graph"}],
                "tests": [
                    {
                        "name": "case",
                        "models": [SOURCE_MODEL],
                        "assertions": [VALID_ASSERTION],
                    }
                ],
            }
        )

        # The assertion names a `Graph` model the response never declared. The
        # metamodel list must not become one.
        with self.assertRaises(SemanticCasesError):
            parse(raw)

    def test_declared_models_are_never_duplicated_by_the_metamodel_list(self) -> None:
        raw = json.dumps(
            {
                "schemaVersion": 1,
                "transformation": "transformations/Tree2Graph.etl",
                "metamodels": [
                    {"name": "Tree", "uri": "Tree"},
                    {"name": "Graph", "uri": "Graph"},
                ],
                "tests": [
                    {
                        "name": "case",
                        "models": [SOURCE_MODEL, TARGET_MODEL],
                        "assertions": [VALID_ASSERTION],
                    }
                ],
            }
        )

        spec = parse(raw)

        self.assertEqual(
            ["Tree", "Graph"], [m["name"] for m in spec["tests"][0]["models"]]
        )


class RepresentationNormalizationStillAppliesTests(unittest.TestCase):
    """The allowed half of the module must keep working."""

    def test_the_transformation_extension_is_canonicalized(self) -> None:
        raw = json.dumps(
            {
                "schemaVersion": 1,
                "transformation": "Tree2Graph",
                "tests": [
                    {
                        "name": "case",
                        "models": [SOURCE_MODEL, TARGET_MODEL],
                        "assertions": [VALID_ASSERTION],
                    }
                ],
            }
        )

        self.assertEqual("transformations/Tree2Graph.etl", parse(raw)["transformation"])

    def test_a_string_schema_version_is_canonicalized(self) -> None:
        raw = json.loads(spec_with(VALID_ASSERTION))
        raw["schema_version"] = "1.0"
        del raw["schemaVersion"]

        self.assertEqual(1, parse(json.dumps(raw))["schemaVersion"])

    def test_spec_level_models_are_materialized_onto_each_test(self) -> None:
        raw = json.dumps(
            {
                "schemaVersion": 1,
                "transformation": "transformations/Tree2Graph.etl",
                "models": [SOURCE_MODEL, TARGET_MODEL],
                "tests": [{"name": "case", "assertions": [VALID_ASSERTION]}],
            }
        )

        spec = parse(raw)

        self.assertEqual(
            ["Tree", "Graph"], [m["name"] for m in spec["tests"][0]["models"]]
        )

    def test_metamodel_path_precedence_and_passthrough_are_preserved(self) -> None:
        malformed = {"unexpected": "shape"}
        self.assertEqual(
            [
                "explicit.ecore",
                "metamodels/ByUri.ecore",
                "metamodels/ByName.ecore",
                "already-a-path.ecore",
                malformed,
                7,
            ],
            normalize_metamodels(
                [
                    {"path": "explicit.ecore", "uri": "ignored"},
                    {"uri": "ByUri", "name": "ignored"},
                    {"name": "ByName"},
                    "already-a-path.ecore",
                    malformed,
                    7,
                ]
            ),
        )


class NoUndefinedExpectedValuesTests(unittest.TestCase):
    """A value the contract does not define must not be given one by the emitter.

    `null` in an expected pair used to reach Java generation, where Python's
    f-string turned it into the literal text "None" — while one Java emitter
    would have printed `null` and the other the string "null" for the observed
    side. Three spellings of "absent", none of them defined anywhere.
    """

    def reference_pairs(self, expected: list) -> str:
        return spec_with(
            {
                "kind": "referencePairs",
                "model": "Graph",
                "type": "Edge",
                "source": "source.name",
                "target": "target.name",
                "expected": expected,
            }
        )

    def test_a_pair_with_a_null_target_is_rejected(self) -> None:
        with self.assertRaisesRegex(SemanticCasesError, "no target identity"):
            parse(self.reference_pairs([{"source": "a", "target": None}]))

    def test_a_pair_with_a_null_source_is_rejected(self) -> None:
        with self.assertRaisesRegex(SemanticCasesError, "no source identity"):
            parse(self.reference_pairs([{"source": None, "target": "b"}]))

    def test_a_pair_missing_an_endpoint_entirely_is_rejected(self) -> None:
        with self.assertRaisesRegex(SemanticCasesError, "no target identity"):
            parse(self.reference_pairs([{"source": "a"}]))

    def test_complete_pairs_are_accepted(self) -> None:
        spec = parse(self.reference_pairs([{"source": "a", "target": "b"}]))

        self.assertEqual(
            [{"source": "a", "target": "b"}],
            spec["tests"][0]["assertions"][0]["expected"],
        )

    def test_an_expected_object_missing_a_declared_feature_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            SemanticCasesError, "no value for declared feature"
        ):
            parse(
                spec_with(
                    {
                        "kind": "objects",
                        "model": "Graph",
                        "type": "Node",
                        "features": ["name", "label"],
                        "expected": [{"name": "a", "label": None}],
                    }
                )
            )

    def test_no_java_is_rendered_for_a_specification_with_a_null_endpoint(self) -> None:
        generated, validation = render_generated_suite(
            "Tree2Graph",
            {
                SEMANTIC_CASES_FILE: self.reference_pairs(
                    [{"source": "a", "target": None}]
                )
            },
            language="etl",
            config=ETL_CONFIG,
            transformation_extension=".etl",
            render_test=render_semantic_test,
        )

        self.assertFalse(validation.valid)
        self.assertEqual(INVALID_SEMANTIC_CASES, validation.reason_code)
        # The corruption this replaces was a rendered `"a->None"` expectation.
        self.assertEqual([], [name for name in generated if name.endswith(".java")])
        self.assertNotIn("None", json.dumps(generated))


class AmbiguityBecomesAnInvalidCandidateTests(unittest.TestCase):

    def test_a_malformed_specification_yields_an_invalid_artifact_not_a_crash(
        self,
    ) -> None:
        extracted = {
            SEMANTIC_CASES_FILE: spec_with(
                {
                    "kind": "featureValues",
                    "model": "Graph",
                    "type": "Node",
                    "feature": "name",
                    "where": {"name": "root"},
                }
            )
        }

        generated, validation = render_generated_suite(
            "Tree2Graph",
            extracted,
            language="etl",
            config=ETL_CONFIG,
            transformation_extension=".etl",
            render_test=render_semantic_test,
        )

        self.assertFalse(validation.valid)
        self.assertEqual(INVALID_SEMANTIC_CASES, validation.reason_code)
        self.assertTrue(validation.violations)
        # The candidate is still written, so it stays in the RQ1 denominator.
        self.assertIn(SEMANTIC_CASES_FILE, generated)

    def test_a_model_entry_of_the_wrong_shape_is_reported_not_dropped(self) -> None:
        raw = json.dumps(
            {
                "schemaVersion": 1,
                "transformation": "transformations/Tree2Graph.etl",
                "tests": [
                    {
                        "name": "case",
                        "models": [SOURCE_MODEL, "Graph"],
                        "assertions": [VALID_ASSERTION],
                    }
                ],
            }
        )

        with self.assertRaisesRegex(SemanticCasesError, "must be an object"):
            parse(raw)


if __name__ == "__main__":
    unittest.main()
