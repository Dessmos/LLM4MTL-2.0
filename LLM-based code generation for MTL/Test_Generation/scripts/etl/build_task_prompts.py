#!/usr/bin/env python3
"""Build deterministic ETL test-generation prompts from task contracts."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from etl.prompt_generation.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
