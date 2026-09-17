"""The closed vocabularies every layer must spell identically.

Model families and prompting strategies name directories, workflow exports,
manifest axes and experiment matrices. Each of those readers selects by exact
string, so a second spelling anywhere produces artifacts no other layer can find:
QVT-O once spelled the strategies ``zero_shot`` and ``few_shot_AND_grammar``, and
its results were selectable by no matrix. This module is the one place the
spellings live; the n8n export synchronizer, the experiment configuration and the
tests import them from here.

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
