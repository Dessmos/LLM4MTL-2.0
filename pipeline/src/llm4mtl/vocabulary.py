"""The closed vocabularies every layer must spell identically.

Model families and prompting strategies name directories, workflow exports,
manifest axes and experiment matrices. Every reader selects by exact string, so
a second spelling produces artifacts no other layer can find (a QVT-O
``zero_shot`` strategy once made its results invisible to every matrix). This
module is the one place the spellings live; the n8n export synchronizer, the
experiment configuration and the tests import them from here.

The contract stage ids are the same kind of spelling: n8n sends them, run
directories are named after them, and diagnosis and refinement read those
directories back.

The artifact tree is one directory per model *family*, not per exact provider
model id: every ``gpt-5`` build writes under ``gpt-5``. The exact id stays in the
n8n model node.
"""

from __future__ import annotations

# The three cloud families the thesis experiment compares.
EXPERIMENT_MODEL_FAMILIES: tuple[str, ...] = (
    "gpt-5",
    "claude-sonnet-4",
    "gemini-2-5-pro",
)

# The local model the smoke workflows run; never part of the experiment.
LOCAL_SMOKE_MODEL_FAMILY = "qwen2-5-coder-7b"

# Every family a workflow export exists for.
MODEL_FAMILIES: tuple[str, ...] = (*EXPERIMENT_MODEL_FAMILIES, LOCAL_SMOKE_MODEL_FAMILY)

# The prompting axis, in the order experiments/matrices/*.yaml lists it.
STRATEGIES: tuple[str, ...] = (
    "only_prompt",
    "grammar",
    "few_shot",
    "few_shots_AND_grammar",
)

# Contract stage ids, as docs/n8n-python-contract.md spells them.
EXTRACT_STAGE_ID = "extract"
SYNTAX_VALIDATION_STAGE_ID = "syntax-validation"
TECHNICAL_VALIDATION_STAGE_ID = "technical-validation"
REFERENCE_VALIDATION_STAGE_ID = "reference-validation"
EXECUTION_STAGE_ID = "execution"
