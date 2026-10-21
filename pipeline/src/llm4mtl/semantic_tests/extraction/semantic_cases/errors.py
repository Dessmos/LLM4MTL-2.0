"""Domain failures in an untrusted semantic-case specification."""

from __future__ import annotations


class SemanticCasesError(ValueError):
    """The generated semantic-case document cannot become an executable suite."""
