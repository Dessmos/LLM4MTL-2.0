"""Stable references to the artifacts a stage consumed or produced.

An observation is only reproducible if it names the exact bytes it was made
from. A path alone is not enough: the reference transformation, a task contract,
or a generated suite can all change under the same path, and a stored result
would then claim to be about inputs it never saw.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArtifactRef:
    """One artifact, identified by where it is and what it contained."""

    path: str
    sha256: str
    role: str

    def __post_init__(self) -> None:
        if not self.path or not self.role:
            raise ValueError("an artifact reference needs a path and a role")
        if len(self.sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.sha256
        ):
            raise ValueError(f"{self.path}: sha256 must be a lower-case SHA-256 digest")

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "role": self.role}
