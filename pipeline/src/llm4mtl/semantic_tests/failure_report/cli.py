"""Narrow local entry point for assembling one report from a request file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from llm4mtl.semantic_tests.failure_report import write_report
from llm4mtl.semantic_tests.failure_report.artifacts import _repository_path
from llm4mtl.semantic_tests.failure_report.errors import FailureReportError
from llm4mtl.semantic_tests.failure_report.request import (
    REQUEST_TYPES,
    _output_path,
    read_request_payload,
)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble one immutable semantic failure report."
    )
    parser.add_argument("--request", type=Path, required=True, help="JSON request file")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="new report path below artifacts/work",
    )
    parser.add_argument(
        "--scope",
        choices=sorted(REQUEST_TYPES),
        default="test_case",
        help="which kind of failure the request records",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; returns non-zero without writing a partial report."""
    args = _parse_args(argv)
    try:
        payload = read_request_payload(args.request)
        write_report(payload, args.output, scope=args.scope)
    except (FailureReportError, FileExistsError, json.JSONDecodeError, OSError) as exc:
        print(f"failure report error: {exc}", file=sys.stderr)
        return 2
    print(_repository_path(_output_path(args.output)))
    return 0
