"""Atomic allocation of attempt directories.

Reading the highest existing attempt number and then writing it back is a
read-then-write race: two stage calls for the same stage (an n8n retry, a
parallel branch, an ablation fan-out) both compute the same number and the
second silently overwrites the first attempt's evidence.

Claiming the directory itself with ``mkdir(exist_ok=False)`` makes the winner
explicit — the filesystem decides — and the loser simply advances to the next
free number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

# A stage cannot legitimately need more attempts than this within one run; the
# bound turns a pathological state into a loud failure instead of a hang.
MAX_ATTEMPTS = 1000


class AttemptAllocationError(RuntimeError):
    """Raised when no free attempt number could be claimed."""


ATTEMPT_PREFIX = "attempt-"


def claim_attempt(
    attempts_root: Path,
    attempt_dir: Callable[[int], Path],
    *,
    prefix: str = ATTEMPT_PREFIX,
) -> int:
    """Create the next free numbered directory and return its 1-based number.

    ``prefix`` is what the existing directories are named with, so the same
    claim serves ``attempt-NNN`` and any other monotonic sequence (a batch of
    runs claims ``batch_NNN`` the same way).
    """
    attempts_root.mkdir(parents=True, exist_ok=True)
    attempt = next_free_number(attempts_root, prefix=prefix)
    while attempt <= MAX_ATTEMPTS:
        try:
            attempt_dir(attempt).mkdir(parents=False, exist_ok=False)
        except FileExistsError:
            attempt += 1
            continue
        return attempt
    raise AttemptAllocationError(
        f"no free attempt number below {MAX_ATTEMPTS} in {attempts_root}"
    )


def next_free_number(attempts_root: Path, *, prefix: str = ATTEMPT_PREFIX) -> int:
    """One past the highest existing number, so numbering stays monotonic.

    A preview only: nothing is claimed, so two callers can read the same value.
    """
    return max(existing_attempts(attempts_root, prefix=prefix), default=0) + 1


def existing_attempts(attempts_root: Path, *, prefix: str = ATTEMPT_PREFIX) -> list[int]:
    """Numbers already present, ignoring unrelated directory entries."""
    if not attempts_root.is_dir():
        return []
    numbers = []
    for item in attempts_root.glob(f"{prefix}*"):
        suffix = item.name[len(prefix) :]
        if item.is_dir() and suffix.isdigit():
            numbers.append(int(suffix))
    return numbers
