#!/usr/bin/env python3
"""Validate generated ETL semantic suites against reference transformations."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from llm4mtl.semantic_tests.reference_validation.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
