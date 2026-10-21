"""Fixed Java source that renderers copy into generated files unchanged.

Each language package keeps this text in a ``java/`` folder next to its
renderer, as ``<name>.java.txt`` files. Keeping Java in Java files, rather than
in Python string lists, lets a reader see the harness code as it is emitted.
The ``.txt`` suffix keeps build tools from compiling these files on their own.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

JAVA_RESOURCE_DIR = "java"


@cache
def java_text(package: str, name: str) -> str:
    """The full text of resource ``name`` in ``package``'s ``java/`` folder."""
    resource = files(package).joinpath(JAVA_RESOURCE_DIR, name)
    return resource.read_text(encoding="utf-8")


def java_lines(package: str, name: str) -> list[str]:
    """The lines of a resource, ready to join with ``"\\n"`` into Java source.

    The file's final line break only ends the file; it is not an extra line.
    """
    return java_text(package, name).removesuffix("\n").split("\n")
