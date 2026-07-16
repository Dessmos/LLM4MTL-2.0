#!/usr/bin/env python3
"""Execute validated generated tests against LLM-generated ETL transformations."""

from __future__ import annotations

import sys
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[2]
TEST_GENERATION_SCRIPTS = REPO_ROOT / "Test_Generation" / "scripts"

for import_root in (THIS_DIR, TEST_GENERATION_SCRIPTS):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from transformation_validation.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
