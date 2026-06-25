#!/usr/bin/env python3
"""Extract generated ETL semantic test suites from n8n Markdown responses."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from etl.extraction.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
