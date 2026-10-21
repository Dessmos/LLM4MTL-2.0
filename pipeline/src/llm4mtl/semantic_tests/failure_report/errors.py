"""The one failure mode of report assembly."""

from __future__ import annotations


class FailureReportError(ValueError):
    """Raised when recorded evidence cannot form a trustworthy report."""
