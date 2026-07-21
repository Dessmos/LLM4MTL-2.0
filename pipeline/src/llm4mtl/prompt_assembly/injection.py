"""Idempotent injection of deterministic marked blocks into a prompt.

Used to overlay the authoritative contract header and task-context block onto an
LLM-authored test-generation prompt, replacing them in place on re-runs.
"""

from __future__ import annotations


def inject_marked_block(
    text: str,
    start_marker: str,
    end_marker: str,
    block: str,
    anchor_after: str | None = None,
) -> str:
    """Insert or replace a ``start_marker … end_marker`` region with ``block``.

    ``block`` must already contain its own start/end markers. If the region
    exists it is replaced in place; otherwise the block is inserted right after
    ``anchor_after`` (when given and present) or prepended to the top.
    """
    if start_marker in text and end_marker in text:
        before, rest = text.split(start_marker, 1)
        _, after = rest.split(end_marker, 1)
        return before + block + after

    if anchor_after and anchor_after in text:
        head, tail = text.split(anchor_after, 1)
        return head + anchor_after + "\n\n" + block + "\n" + tail.lstrip("\n")

    return block + "\n\n" + text
