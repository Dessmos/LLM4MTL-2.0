"""``python -m llm4mtl.prompt_assembly.n8n_exports`` entry point."""

from __future__ import annotations

from llm4mtl.prompt_assembly.n8n_exports.sync import main

if __name__ == "__main__":
    raise SystemExit(main())
