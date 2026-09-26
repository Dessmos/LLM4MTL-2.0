"""JSON document read/write helpers.

Both writers stage the complete document in a temporary file beside the target
and fsync it before it becomes visible, so a reader never sees a half-written
document. They differ only in how the staged file becomes the target: an atomic
replace, or an atomic create that refuses an existing document.

:func:`write_json_once_or_match` builds on the atomic create for records that
are written once but may be reported again by a retry.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

Document = dict[str, Any]


def write_json(path: Path, payload: Any) -> None:
    """Atomically replace ``path`` with one complete JSON document."""
    path = Path(path)
    staged = _stage_document(path, payload)
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def write_json_once(path: Path, payload: Any) -> None:
    """Atomically create ``path``; raise :class:`FileExistsError` when it exists.

    A hard link is an atomic create-if-absent operation. Unlike ``exists()``
    followed by a write, concurrent creators have exactly one winner, and the
    winner's document is never replaced.
    """
    path = Path(path)
    staged = _stage_document(path, payload)
    try:
        os.link(staged, path)
    finally:
        staged.unlink(missing_ok=True)


class JsonDocumentConflictError(ValueError):
    """Raised when a write-once document already holds different content.

    ``stored`` is the document that was there first, so the caller can say
    what the earlier writer recorded.
    """

    def __init__(self, path: Path, stored: Document) -> None:
        super().__init__(f"a different document already exists: {path}")
        self.path = path
        self.stored = stored


def write_json_once_or_match(
    path: Path,
    payload: Document,
    *,
    comparable: Callable[[Document], Document],
    check_stored: Callable[[Document], None] | None = None,
) -> Document:
    """Create ``path`` once, or accept the same document written earlier.

    Returns the stored document: ``payload`` when this call created the file,
    or the earlier document when both are equal after ``comparable``. A retry
    may legitimately move a timestamp, so ``comparable`` drops such fields.
    ``check_stored`` validates the earlier document before the comparison.

    The create is atomic, so of two concurrent writers exactly one wins and
    the other compares against the winner. Raises
    :class:`JsonDocumentConflictError` when the earlier document differs.
    """
    path = Path(path)
    try:
        write_json_once(path, payload)
    except FileExistsError:
        stored = read_json(path)
        if check_stored is not None:
            check_stored(stored)
        if comparable(stored) != comparable(payload):
            raise JsonDocumentConflictError(path, stored) from None
        return stored
    return payload


def read_json(path: Path) -> Any:
    """Parse the JSON document at ``path``."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stage_document(path: Path, payload: Any) -> Path:
    """Write ``payload`` as JSON to a fsynced temporary file beside ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    staged = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        staged.unlink(missing_ok=True)
        raise
    return staged
