"""The export walk infers a workflow's language from the path below its root."""

from __future__ import annotations

import unittest
from pathlib import Path

from llm4mtl.prompt_assembly.n8n_exports.sync import _language_from_workflow_path

# A checkout whose folder names contain every language name.
CHECKOUT = Path("/home/atlas/qvto-reactions-etl/LLM4MTL")
WORKFLOWS_ROOT = CHECKOUT / "workflows" / "n8n" / "transformations" / "workflows"


class LanguageFromWorkflowPathTests(unittest.TestCase):

    def test_the_checkout_location_does_not_change_the_language(self) -> None:
        for language in ("etl", "atl", "qvto", "reactions"):
            path = (
                WORKFLOWS_ROOT
                / f"{language}_variants"
                / f"Prompt_generation_{language}.json"
            )
            with self.subTest(language=language):
                self.assertEqual(
                    language,
                    _language_from_workflow_path(path, WORKFLOWS_ROOT),
                )

    def test_a_path_without_a_language_below_the_root_is_rejected(self) -> None:
        path = WORKFLOWS_ROOT / "shared" / "Prompt_generation.json"

        with self.assertRaisesRegex(ValueError, "cannot infer workflow language"):
            _language_from_workflow_path(path, WORKFLOWS_ROOT)


if __name__ == "__main__":
    unittest.main()
