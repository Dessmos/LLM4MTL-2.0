"""How the file under test is prepared before the harness runs it.

Two steps, both on a scratch copy; the generated artifact is never changed:

* Its segment gets the task's name (``rendering.segment_name``). Other
  languages place the transformation at a fixed file name; for Reactions the
  segment name is what the test looks the transformation up by.
* The reactions it presupposes join that segment. A reaction that retrieves a
  correspondence cannot act until another task's reaction has created it. The
  task contract names those prerequisite tasks, and their reference reactions
  are merged in.
"""

from __future__ import annotations

import json
import re

from llm4mtl.conventions import REACTIONS_CONFIG, default_task_contracts_root

SEGMENT_START = re.compile(r"^reactions:", re.MULTILINE)
SEGMENT_NAME = re.compile(r"^reactions:[ \t]*(\w+)", re.MULTILINE)
HEADER_END = re.compile(r"^\s*execute\s+actions\s+in\b[^\n]*$", re.MULTILINE)
METAMODEL_IMPORT = re.compile(r'^\s*import\s+"[^"]+"\s+as\s+\w+[^\n]*$', re.MULTILINE)
ROUTINE_NAME = re.compile(r"^\s*routine\s+(\w+)", re.MULTILINE)


class UnmergeableTransformationError(Exception):
    """The transformation under test cannot share a segment with its prerequisites.

    The cause is in the transformation itself: it has no named reactions
    segment, or it reuses a routine name of a prerequisite. So it is recorded as the
    transformation failing to load, not as a broken harness.
    """


def prerequisite_tasks(task: str) -> tuple[str, ...]:
    """Tasks whose reactions must run alongside this one, prerequisites first.

    Reads ``prerequisiteTasks`` from each task contract and follows the chain.
    Raises ``ValueError`` on a cycle.
    """
    root = default_task_contracts_root(REACTIONS_CONFIG)
    ordered: list[str] = []

    def walk(name: str, seen: tuple[str, ...]) -> None:
        if name in seen:
            raise ValueError(f"prerequisite cycle through {name!r}")
        path = root / f"{name}.json"
        if not path.is_file():
            return
        contract = json.loads(path.read_text(encoding="utf-8"))
        for prerequisite in contract.get("prerequisiteTasks") or ():
            walk(str(prerequisite), (*seen, name))
            if prerequisite not in ordered:
                ordered.append(str(prerequisite))

    walk(task, ())
    return tuple(ordered)


def bind_segment(base: str, name: str) -> str:
    """``base`` with its first reactions segment named ``name``.

    Only the first segment is renamed: it is the one the test runs, and the one
    prerequisites join. Raises :class:`UnmergeableTransformationError` when the
    transformation declares no named segment.
    """
    declared = SEGMENT_NAME.search(base)
    if declared is None:
        raise UnmergeableTransformationError(
            "transformation declares no reactions segment"
        )
    return base[: declared.start(1)] + name + base[declared.end(1) :]


def merge_reactions(base: str, prerequisites: list[str]) -> str:
    """Put every prerequisite's reactions into the base file's one segment.

    Raises :class:`UnmergeableTransformationError` for a defect of ``base``.
    Raises ``ValueError`` for a malformed prerequisite reference, which is a
    benchmark defect, not a fact about the artifact under test.
    """
    start = SEGMENT_START.search(base)
    if start is None:
        raise UnmergeableTransformationError(
            "transformation declares no reactions segment"
        )
    head, segment = base[: start.start()], base[start.start() :]
    imports = set(METAMODEL_IMPORT.findall(head))
    routines = set(ROUTINE_NAME.findall(base))

    bodies = []
    for prerequisite in prerequisites:
        for statement in METAMODEL_IMPORT.findall(prerequisite):
            if statement.strip() not in {value.strip() for value in imports}:
                imports.add(statement)
                head = head.rstrip("\n") + "\n" + statement.strip() + "\n"
        header = HEADER_END.search(prerequisite)
        if header is None:
            raise ValueError("prerequisite declares no reactions segment header")
        body = prerequisite[header.end() :]
        clashing = routines & set(ROUTINE_NAME.findall(body))
        if clashing:
            raise UnmergeableTransformationError(
                "prerequisite reuses routine names of the transformation under "
                f"test: {', '.join(sorted(clashing))}"
            )
        routines |= set(ROUTINE_NAME.findall(body))
        bodies.append(body.strip("\n"))

    return "\n".join([head.rstrip("\n"), "", segment.rstrip("\n"), "", *bodies, ""])
