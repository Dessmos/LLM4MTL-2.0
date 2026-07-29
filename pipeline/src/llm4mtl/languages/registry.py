"""Which language adapters exist.

Static and explicit on purpose. There are exactly four known languages and no
third-party extension point, so discovery by import scanning or entry points
would add indirection without a caller that needs it. Adding a language means
adding one line here and one adapter module.

A language the pipeline cannot yet run fails loudly at this seam. That is the
point: silently falling back to ETL conventions would produce results attributed
to a language that never ran.
"""

from __future__ import annotations

from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.languages.etl.adapter import EtlAdapter

# Every language the thesis must cover, and whether an adapter exists yet.
REQUIRED_LANGUAGES: tuple[str, ...] = ("etl", "atl", "qvto", "reactions")

_ADAPTERS: dict[str, LanguageAdapter] = {
    "etl": EtlAdapter(),
}


class UnsupportedLanguageError(KeyError):
    """Raised when no adapter implements the requested language yet."""


def language_adapter(language: str) -> LanguageAdapter:
    """The adapter for ``language``, or a clear failure naming what is missing."""
    key = language.lower()
    if key in _ADAPTERS:
        return _ADAPTERS[key]
    if key in REQUIRED_LANGUAGES:
        raise UnsupportedLanguageError(
            f"no language adapter for '{key}' yet; it is required for the thesis "
            f"but not implemented (implemented: {', '.join(sorted(_ADAPTERS))})"
        )
    raise UnsupportedLanguageError(
        f"unknown language '{language}' (known: {', '.join(REQUIRED_LANGUAGES)})"
    )


def implemented_languages() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))
