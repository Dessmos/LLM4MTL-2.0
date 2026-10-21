"""Stable references to the artifacts a stage consumed or produced.

An observation is only reproducible if it names the exact bytes it was made
from. A path alone is not enough: the reference transformation, a task contract,
or a generated suite can all change under the same path, and a stored result
would then claim to be about inputs it never saw.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactRef:
    """One artifact, identified by where it is and what it contained."""

    path: str
    sha256: str
    role: str

    def __post_init__(self) -> None:
        if not self.path or not self.role:
            raise ValueError("an artifact reference needs a path and a role")
        if not _is_lowercase_sha256(self.sha256):
            raise ValueError(f"{self.path}: sha256 must be a lower-case SHA-256 digest")

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256, "role": self.role}


def _is_lowercase_sha256(digest: str) -> bool:
    return len(digest) == 64 and all(
        character in "0123456789abcdef" for character in digest
    )
