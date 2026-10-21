"""Language-specific execution behind one explicit boundary.

Shared pipeline code does not name a language. It gets an adapter from the
registry and calls the small interface in :mod:`llm4mtl.languages.base`. Each
adapter owns its parser, harness, file conventions, and failure mapping, and
reports its results with the types from :mod:`llm4mtl.domain`.
"""

from __future__ import annotations

from llm4mtl.languages.base import LanguageAdapter, Workspace
from llm4mtl.languages.registry import (
    REQUIRED_LANGUAGES,
    UnsupportedLanguageError,
    language_adapter,
)

__all__ = [
    "LanguageAdapter",
    "REQUIRED_LANGUAGES",
    "UnsupportedLanguageError",
    "Workspace",
    "language_adapter",
]
