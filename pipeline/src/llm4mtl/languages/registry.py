"""Which language adapters exist.

The list is static on purpose: there are four known languages and no plug-in
point. Adding a language means adding one line here and one adapter package.

An unknown language fails loudly here. Falling back to ETL instead would record
results for a language that never ran.
"""

from __future__ import annotations

from llm4mtl.languages.atl.adapter import AtlAdapter
from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.languages.etl.adapter import EtlAdapter
from llm4mtl.languages.qvto.adapter import QvtoAdapter
from llm4mtl.languages.reactions.adapter import ReactionsAdapter

REQUIRED_LANGUAGES: tuple[str, ...] = ("etl", "atl", "qvto", "reactions")

_ADAPTERS: dict[str, LanguageAdapter] = {
    "etl": EtlAdapter(),
    "atl": AtlAdapter(),
    "qvto": QvtoAdapter(),
    "reactions": ReactionsAdapter(),
}


class UnsupportedLanguageError(KeyError):
    """Raised when no adapter implements the requested language."""


def language_adapter(language: str) -> LanguageAdapter:
    """The adapter for ``language``, or a clear failure naming what is missing."""
    key = language.lower()
    if key in _ADAPTERS:
        return _ADAPTERS[key]
    raise UnsupportedLanguageError(
        f"unknown language '{language}' (known: {', '.join(REQUIRED_LANGUAGES)})"
    )
