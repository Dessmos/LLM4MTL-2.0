"""Extract one generated semantic-test response into an immutable candidate suite.

The library entry point of the ``extract`` stage.
"""

from __future__ import annotations

from llm4mtl.domain import EXTRACTION_FAILED
from llm4mtl.languages.base import LanguageAdapter
from llm4mtl.semantic_tests.extraction.models import (
    ExtractionError,
    ExtractionOptions,
    ResponseTarget,
)
from llm4mtl.semantic_tests.extraction.parser import extract_files
from llm4mtl.semantic_tests.extraction.writer import write_failed_candidate, write_suite


def extract_one(
    target: ResponseTarget,
    options: ExtractionOptions,
    adapter: LanguageAdapter,
) -> tuple[bool, str]:
    """Extract one response. Returns whether it yielded a usable suite, and why not.

    An artifact-invalid suite is still written: it is the evidence behind the
    funnel's artifact-valid rate, and dropping it would quietly shrink that
    denominator. It is reported as a failure because the response did not
    produce a usable semantic-test specification.
    """
    if not target.response_path.exists():
        return False, f"response not found: {target.response_path}"

    markdown = target.response_path.read_text(encoding="utf-8")
    try:
        extracted = extract_files(markdown)
    except ExtractionError as exc:
        return _failed_candidate(target, options, adapter, str(exc))
    if not extracted:
        return _failed_candidate(
            target,
            options,
            adapter,
            f"no fenced file block found in {target.response_path.name}",
        )

    suite_dir, validation = write_suite(target, extracted, options, adapter)
    if not validation.valid:
        reason = "; ".join(validation.violations)
        return (
            False,
            f"wrote {suite_dir} [INVALID: {validation.reason_code}] {reason}",
        )
    return True, f"wrote {suite_dir}"


def _failed_candidate(
    target: ResponseTarget,
    options: ExtractionOptions,
    adapter: LanguageAdapter,
    reason: str,
) -> tuple[bool, str]:
    """Persist an unreadable response as an invalid candidate and keep going.

    The response stays countable in every stage that follows: it is selected
    like any other candidate, refused at artifact validation, and therefore
    never executed. Dropping it instead would shrink the invalid-test rate's
    denominator by exactly the responses that deserve to be in it.
    """
    suite_dir, validation = write_failed_candidate(
        target,
        options,
        adapter,
        reason_code=EXTRACTION_FAILED,
        violations=(reason,),
    )
    return False, f"recorded {suite_dir} [INVALID: {validation.reason_code}] {reason}"
