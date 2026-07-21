#!/usr/bin/env python3
"""Execute validated generated tests against LLM-generated ETL transformations."""

from __future__ import annotations

import sys
from pathlib import Path


# Allow running this script directly without an editable install by putting the
# pipeline/ directory (which contains the llm4mtl package) on sys.path.
_PIPELINE_DIR = Path(__file__).resolve().parents[2]
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from llm4mtl.transformation_execution.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
