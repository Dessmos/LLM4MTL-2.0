#!/usr/bin/env bash
#
# Capture a behavioural baseline BEFORE the v5 migration moves anything.
#
# The snapshot is written to baseline/snapshot-<timestamp>/ (git-ignored) so it
# can be diffed against the same capture taken AFTER engines are moved (Stage 2).
# Engines are only relocated, never edited, so their test outcomes must match.
#
# Usage:
#   baseline/capture_baseline.sh            # cheap parts: versions + CSV snapshot
#   RUN_MVN=1 baseline/capture_baseline.sh  # also run `mvn test` per engine (slow)
#   RUN_PYTEST=1 baseline/capture_baseline.sh  # also run the Python test suites
#
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="$REPO_ROOT/LLM-based code generation for MTL"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$REPO_ROOT/baseline/snapshot-$STAMP"
mkdir -p "$OUT/csv" "$OUT/logs"

echo "== baseline snapshot: $OUT =="

# 1. Tool versions ------------------------------------------------------------
{
  echo "captured_at=$STAMP"
  echo "git_commit=$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null)"
  echo "git_branch=$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  echo "python=$(python3 --version 2>&1)"
  echo "java=$(java -version 2>&1 | head -1)"
  echo "maven=$(mvn -version 2>&1 | head -1)"
} > "$OUT/versions.txt"

# 2. Snapshot committed result CSVs (the current reference outputs) -----------
find "$PROJECT" -name '*.csv' \
  -not -path '*/target/*' -not -path '*/.git/*' 2>/dev/null | while read -r f; do
    rel="${f#"$PROJECT"/}"
    dest="$OUT/csv/$rel"
    mkdir -p "$(dirname "$dest")"
    cp "$f" "$dest"
done
echo "csv snapshot: $(find "$OUT/csv" -name '*.csv' | wc -l | tr -d ' ') files"

# 3. Optional: engine mvn test (slow; opt in with RUN_MVN=1) ------------------
# Engines were relocated to engines/<lang>/{parser,harness} in migration Stage 2.
if [[ "${RUN_MVN:-0}" == "1" ]]; then
  for engine in etl/parser etl/harness atl/parser atl/harness qvto/parser \
                "qvto/harness/qvto-tests" reactions/parser reactions/harness; do
    dir="$REPO_ROOT/engines/$engine"
    [[ -f "$dir/pom.xml" ]] || { echo "skip (no pom): $engine"; continue; }
    log="$OUT/logs/mvn-$(echo "$engine" | tr '/ ' '__').log"
    echo "mvn test: $engine"
    (cd "$dir" && mvn -q test) > "$log" 2>&1
    echo "  exit=$? -> $log"
  done
fi

# 4. Optional: Python test suites (opt in with RUN_PYTEST=1) ------------------
if [[ "${RUN_PYTEST:-0}" == "1" ]]; then
  if python3 -m pytest --version >/dev/null 2>&1; then
    (cd "$PROJECT" && python3 -m pytest) > "$OUT/logs/pytest.log" 2>&1
    echo "pytest exit=$? -> $OUT/logs/pytest.log"
  else
    echo "pytest not installed; skipping (install: python3 -m pip install pytest)"
  fi
fi

echo "== done: $OUT =="
