"""Which language adapters exist.

Static and explicit on purpose. There are exactly four known languages and no
third-party extension point, so discovery by import scanning or entry points
would add indirection without a caller that needs it. Adding a language means
adding one line here and one adapter module.

A language the pipeline does not recognize fails loudly at this seam. That is the
point: silently falling back to ETL conventions would produce results attributed
to a language that never ran.
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
    """Raised when no adapter implements the requested language yet."""


def language_adapter(language: str) -> LanguageAdapter:
    """The adapter for ``language``, or a clear failure naming what is missing."""
    key = language.lower()
    if key in _ADAPTERS:
        return _ADAPTERS[key]
    raise UnsupportedLanguageError(
        f"unknown language '{language}' (known: {', '.join(REQUIRED_LANGUAGES)})"
    )


def implemented_languages() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
