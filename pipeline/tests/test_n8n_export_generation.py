"""The committed n8n exports are in sync with the generator, which is layered.

A synchronizer rewrites the parts of an export that must not differ between
languages; the rest of each workflow is authored in the n8n editor. So the
committed tree must be a fixed point: running the generator over it changes
nothing. The first test asserts exactly that, by regenerating the whole tree
into a temporary copy and requiring it to come back byte-identical.

What that catches is drift between the generator and its output — a prompt or a
synchronizer edited without re-running ``--write``, which would leave every
affected export stale, and a hand-edit to a field a synchronizer owns, which
the next ``--write`` would silently revert. What it deliberately does not catch
is an edit to a workflow or a field no synchronizer rewrites: those are the
hand-authored parts, and changing them is how they are meant to be changed.

The second test pins the package's layering. ``prompts`` is the module a
reviewer opens to audit what a model is actually asked, and it is only worth
opening if it cannot have acquired workflow plumbing; ``workflow_graph`` is
only generic if it cannot have acquired prompt text. Both are leaves, and
nothing but the facade may depend on more than one layer.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm4mtl.paths import TARGET, TargetLayout
from llm4mtl.prompt_assembly.n8n_exports import synchronize_exports

PACKAGE_DIR = Path(TARGET.package / "prompt_assembly" / "n8n_exports")
# Which sibling modules each module of the package may import. prompts and
# workflow_graph are leaves on purpose: that is what makes either of them
# readable on its own.
ALLOWED_SIBLING_IMPORTS = {
    "prompts.py": set(),
    "workflow_graph.py": set(),
    "synchronizers.py": {"prompts", "workflow_graph"},
    "sync.py": {"synchronizers"},
    "__main__.py": {"sync"},
    "__init__.py": {"sync", "synchronizers"},
}


def sibling_imports(module: Path) -> set[str]:
    """The package's own modules that ``module`` imports."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    prefix = "llm4mtl.prompt_assembly.n8n_exports."
    return {
        node.module[len(prefix) :].split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith(prefix)
    }


class GeneratedExportsAreInSyncTests(unittest.TestCase):

    def test_regenerating_every_export_reproduces_the_committed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shutil.copytree(TARGET.root / "workflows", root / "workflows")
            layout = TargetLayout(root=root)
            with (
                # conventions resolves TARGET at call time; sync bound it at import.
                patch("llm4mtl.paths.TARGET", layout),
                patch("llm4mtl.prompt_assembly.n8n_exports.sync.TARGET", layout),
            ):
                prompts, tests, transformations = synchronize_exports()

            # The walk must actually have found each family of exports; a
            # regenerated-and-identical empty tree would prove nothing.
            self.assertGreater(prompts, 0)
            self.assertGreater(tests, 0)
            self.assertGreater(transformations, 0)

            committed = sorted(TARGET.workflows.rglob("*.json"))
            self.assertGreater(len(committed), 0)
            for path in committed:
                regenerated = root / path.relative_to(TARGET.root)
                with self.subTest(workflow=path.relative_to(TARGET.root).as_posix()):
                    self.assertTrue(regenerated.is_file())
                    self.assertEqual(
                        path.read_bytes(),
                        regenerated.read_bytes(),
                        "committed export differs from what the generator "
                        "produces; edit the generator, not the JSON",
                    )


class ExportPackageLayeringTests(unittest.TestCase):

    def test_each_module_imports_only_the_layer_below_it(self) -> None:
        for name, allowed in sorted(ALLOWED_SIBLING_IMPORTS.items()):
            with self.subTest(module=name):
                self.assertEqual(allowed, sibling_imports(PACKAGE_DIR / name))

    def test_the_package_has_no_modules_outside_the_declared_layering(self) -> None:
        self.assertEqual(
            set(ALLOWED_SIBLING_IMPORTS),
            {path.name for path in PACKAGE_DIR.glob("*.py")},
        )

    def test_the_prompt_module_carries_no_workflow_structure(self) -> None:
        """What a model is asked must be readable without reading n8n plumbing."""
        source = (PACKAGE_DIR / "prompts.py").read_text(encoding="utf-8")
        body = source.split('"""', 2)[2]
        for structural in ('"nodes"', '"connections"', "typeVersion", "n8n-nodes-"):
            with self.subTest(token=structural):
                self.assertNotIn(structural, body)


if __name__ == "__main__":
    unittest.main()
