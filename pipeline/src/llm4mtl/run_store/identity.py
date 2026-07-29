"""Run identifiers and containment of the directories they name.

A ``run_id`` reaches this package from an n8n workflow, a CLI flag, or an
experiment matrix, so it is untrusted input that is turned directly into a
filesystem path. Without the checks here ``../escape`` resolves outside the runs
root and writes a run the aggregation layer can never see.

Ids are opaque: they are compared for equality and used as a directory name, and
nothing downstream parses meaning out of them.
"""

from __future__ import annotations

import re
from pathlib import Path

# Deliberately narrow: the characters used by ``generate_run_id`` and by
# experiment-matrix run ids, and nothing that can traverse or escape a path.
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9._-]+")


class InvalidRunIdError(ValueError):
    """Raised when a run id is malformed or would escape its root directory."""


def validate_opaque_id(identifier: str, *, kind: str = "run") -> None:
    """Require the one-component opaque identifier syntax used in artifact paths."""
    if not isinstance(identifier, str) or not RUN_ID_PATTERN.fullmatch(identifier):
        raise InvalidRunIdError(
            f"invalid {kind} id {identifier!r}: expected a non-empty "
            f"{RUN_ID_PATTERN.pattern} identifier"
        )


def resolve_contained_dir(root: Path, identifier: str, *, kind: str = "run") -> Path:
    """Resolve ``root/identifier`` after proving it stays directly inside ``root``.

    The containment check is on the resolved paths, so it also rejects ids that
    only escape after symlink resolution.
    """
    validate_opaque_id(identifier, kind=kind)

    resolved_root = Path(root).resolve()
    candidate = (resolved_root / identifier).resolve()
    if candidate.parent != resolved_root:
        raise InvalidRunIdError(
            f"invalid {kind} id {identifier!r}: resolves to {candidate}, outside {resolved_root}"
        )
    return candidate
