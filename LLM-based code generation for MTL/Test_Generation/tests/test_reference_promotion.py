from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from etl.reference_validation.promotion import invalid_suite_path, promote_invalid_suite
from etl.suites.models import CandidateSuite


class InvalidPromotionTests(unittest.TestCase):
    def test_reference_invalid_suite_is_copied_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "generated_tests" / "etl"
            candidate = root / "Tree2Graph" / "candidates" / "gpt-5" / "few_shot" / "suite_001"
            candidate.mkdir(parents=True)
            (candidate / "GeneratedTest.java").write_text("class GeneratedTest {}\n", encoding="utf-8")
            suite = CandidateSuite(candidate, "Tree2Graph", "gpt-5", "few_shot", "suite_001")

            destination = promote_invalid_suite(suite, {"status": "REFERENCE_INVALID"})

            self.assertEqual(invalid_suite_path(suite), destination)
            self.assertTrue((destination / "GeneratedTest.java").is_file())
            self.assertTrue((destination / "reference_validation.json").is_file())


if __name__ == "__main__":
    unittest.main()
