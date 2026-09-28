"""A write-once JSON record that a retry may report again.

Run results, batch results, generation records, refinement requests and
adoption metadata are each written once. A retry that reports the same record
must get the stored one back, and a different record must be refused, also when
two writers race.
"""

from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from llm4mtl.serialization import json_io
from llm4mtl.serialization.json_io import (
    JsonDocumentConflictError,
    read_json,
    write_json_once_or_match,
)


def without_time(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "at"}


class WriteJsonOnceOrMatchTests(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "nested" / "record.json"

    def test_a_retry_gets_the_first_record_back(self) -> None:
        write_json_once_or_match(
            self.path, {"status": "done", "at": "1"}, comparable=without_time
        )

        stored = write_json_once_or_match(
            self.path, {"status": "done", "at": "2"}, comparable=without_time
        )

        # The first stamp stays: a retry does not rewrite history.
        self.assertEqual({"status": "done", "at": "1"}, stored)
        self.assertEqual(stored, read_json(self.path))

    def test_a_different_record_is_refused_and_names_the_stored_one(self) -> None:
        write_json_once_or_match(
            self.path, {"status": "done", "at": "1"}, comparable=without_time
        )

        with self.assertRaises(JsonDocumentConflictError) as raised:
            write_json_once_or_match(
                self.path, {"status": "failed", "at": "2"}, comparable=without_time
            )

        self.assertEqual({"status": "done", "at": "1"}, raised.exception.stored)
        self.assertEqual(self.path, raised.exception.path)
        self.assertEqual({"status": "done", "at": "1"}, read_json(self.path))

    def test_the_stored_record_is_checked_before_it_is_compared(self) -> None:
        write_json_once_or_match(self.path, {"status": "done"}, comparable=without_time)

        def refuse(document: dict[str, Any]) -> None:
            raise ValueError(f"invalid stored record: {document}")

        for payload in ({"status": "done"}, {"status": "failed"}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(ValueError, "invalid stored record"):
                    write_json_once_or_match(
                        self.path,
                        payload,
                        comparable=without_time,
                        check_stored=refuse,
                    )

    def test_of_two_racing_writers_exactly_one_record_is_stored(self) -> None:
        payloads = [{"status": "done", "at": "1"}, {"status": "failed", "at": "2"}]
        barrier = threading.Barrier(len(payloads), timeout=10)
        stage_document = json_io._stage_document

        def staged_together(path: Path, payload: Any) -> Path:
            staged = stage_document(path, payload)
            barrier.wait()
            return staged

        outcomes: list[Any] = [None] * len(payloads)

        def write(index: int) -> None:
            try:
                outcomes[index] = write_json_once_or_match(
                    self.path, payloads[index], comparable=without_time
                )
            except JsonDocumentConflictError as exc:
                outcomes[index] = exc

        with patch.object(json_io, "_stage_document", staged_together):
            threads = [threading.Thread(target=write, args=(i,)) for i in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        stored = [outcome for outcome in outcomes if isinstance(outcome, dict)]
        refused = [
            outcome
            for outcome in outcomes
            if isinstance(outcome, JsonDocumentConflictError)
        ]
        self.assertEqual(1, len(stored), outcomes)
        self.assertEqual(1, len(refused), outcomes)
        self.assertEqual(stored[0], read_json(self.path))
        self.assertEqual(stored[0], refused[0].stored)
        # No staged temporary file is left beside the record.
        self.assertEqual(["record.json"], sorted(p.name for p in self.path.parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
