"""Compatibility entry point for the experiment-runner CLI."""

from __future__ import annotations

from llm4mtl.experiment_runner.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
