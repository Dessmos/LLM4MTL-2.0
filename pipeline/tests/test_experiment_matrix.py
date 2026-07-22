from __future__ import annotations

import unittest

from llm4mtl.experiment_runner.matrix import expand_matrix, load_matrix
from llm4mtl.paths import TARGET


class MatrixTests(unittest.TestCase):
    def test_thesis_ablation_expands_to_a_set_of_runs(self) -> None:
        matrix = load_matrix(TARGET.experiments_matrices / "thesis-ablation.yaml")
        specs = expand_matrix(matrix)
        # 2 tasks x 3 transformation models x 4 strategies x 1 test model x 1 test
        # strategy x 4 variants x 1 seed = 96 runs.
        self.assertEqual(96, len(specs))
        self.assertEqual(len(specs), len({spec.run_id for spec in specs}))
        self.assertTrue(all(spec.experiment_id == "thesis-ablation" for spec in specs))
        self.assertEqual(
            {"full", "no-parser-feedback", "no-semantic-feedback", "no-failure-diagnosis"},
            {spec.variant for spec in specs},
        )

    def test_small_matrix_is_a_cartesian_product(self) -> None:
        specs = expand_matrix(
            {
                "experiment_id": "e",
                "language": "etl",
                "tasks": ["A"],
                "transformation_models": ["m1", "m2"],
                "transformation_strategies": ["grammar"],
                "test_models": ["gpt-5"],
                "test_strategies": ["few_shot"],
                "variants": ["full"],
                "seeds": [1, 2],
            }
        )
        self.assertEqual(4, len(specs))  # 1*2*1*1*1*1*2


if __name__ == "__main__":
    unittest.main()
