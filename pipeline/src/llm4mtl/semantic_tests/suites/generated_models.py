"""Where a suite's own model files sit on the harness classpath.

Suite injection copies a suite's ``models/`` folder to this place, and a
renderer writes the same place into the Java test. Both sides use this module,
so the two cannot drift apart.
"""

from __future__ import annotations

from llm4mtl.semantic_tests.semantic_spec import MODELS_DIRECTORY
from llm4mtl.semantic_tests.suites.java import slug

GENERATED_MODELS_DIR = "generated-models"
_SUITE_MODELS_PREFIX = f"{MODELS_DIRECTORY}/"


def generated_models_dir(task: str) -> str:
    """The classpath folder that holds ``task``'s generated model files."""
    return f"{GENERATED_MODELS_DIR}/{slug(task)}"


def generated_model_resource(task: str, path: str) -> str:
    """The classpath resource for a model file the suite names by ``path``.

    ``path`` is relative to the suite root; a leading ``models/`` is dropped
    because that folder's content is what gets copied.
    """
    relative = path.replace("\\", "/").removeprefix(_SUITE_MODELS_PREFIX)
    return f"{generated_models_dir(task)}/{relative}"
