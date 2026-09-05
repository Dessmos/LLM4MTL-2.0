"""The raw evidence one suite execution produced, as pure data.

``execute_suite`` on :class:`~llm4mtl.languages.base.LanguageAdapter` returns
this alongside its observation, so the types belong to the shared vocabulary
rather than to the module that happens to persist them. Keeping them here is
what lets ``languages/base.py`` state its contract without importing a stage.

Nothing here interprets anything. Reading the evidence out of a workspace and
archiving it is :mod:`llm4mtl.semantic_tests.execution_evidence`'s job; these
are the values that travel between the two.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurefireArtifact:
    """One Surefire report file, read verbatim while it still existed."""

    name: str
    content: str


@dataclass(frozen=True)
class RawExecutionEvidence:
    """Everything one Maven invocation produced, held in memory.

    ``reports_present`` is recorded separately from ``reports`` because "the
    directory held no report" and "the reports could not be parsed" are
    different states, and neither may be presented as "the run had no failures".
    ``tests``/``failures``/``errors`` are ``None`` whenever no report parsed.
    """

    exit_code: int | str
    timed_out: bool
    stdout: str
    stderr: str
    reports_present: bool
    reports: tuple[SurefireArtifact, ...] = ()
    tests: int | None = None
    failures: int | None = None
    errors: int | None = None
