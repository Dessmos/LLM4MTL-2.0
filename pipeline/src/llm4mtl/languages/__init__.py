"""Language-specific execution behind one explicit boundary.

The shared pipeline never names a language: it resolves an adapter from the
registry and calls the narrow interface in :mod:`llm4mtl.languages.base`. Each
adapter owns its parser, harness, file conventions, and diagnostic
normalization, and depends on :mod:`llm4mtl.domain` for the vocabulary it
reports in.
"""

from __future__ import annotations

from llm4mtl.languages.base import LanguageAdapter, Workspace
from llm4mtl.languages.registry import (
    REQUIRED_LANGUAGES,
    UnsupportedLanguageError,
    implemented_languages,
    language_adapter,
)

__all__ = [
    "LanguageAdapter",
    "REQUIRED_LANGUAGES",
    "UnsupportedLanguageError",
    "Workspace",
    "implemented_languages",
    "language_adapter",
]
