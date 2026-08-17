"""Identity of one generated test suite.

A suite keeps this identity through the whole funnel — extracted, executed,
judged, promoted — so every observation stays attributable to the same
(language, task, generating model, strategy, suite) combination.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeneratedSuite:
    """One generated suite on disk, with the identity it is attributed to."""

    language: str
    path: Path
    task: str
    llm: str
    strategy: str
    suite_id: str

    def __post_init__(self) -> None:
        identity_values = (
            ("language", self.language),
            ("task", self.task),
            ("llm", self.llm),
            ("strategy", self.strategy),
            ("suite_id", self.suite_id),
        )
        for name, value in identity_values:
            if not value:
                raise ValueError(f"a generated suite needs a non-empty {name}")

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        """The grouping key metrics aggregate by."""
        return (self.language, self.task, self.llm, self.strategy, self.suite_id)
