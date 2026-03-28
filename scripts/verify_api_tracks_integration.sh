#!/usr/bin/env bash
# Verify API issues #31–#34: feature tips are merged into HEAD, then run full pytest.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

git fetch origin --quiet

refs=(
  origin/issue/31-api-lifespan-settings
  origin/issue/32-post-cases-intake
  origin/issue/33-reports-pipeline-stub
  origin/issue/34-arq-worker-and-tests
)
for ref in "${refs[@]}"; do
  if ! git rev-parse --verify -q "$ref" >/dev/null; then
    echo "FAIL: ref $ref does not exist after fetch (remote branch deleted or typo)." >&2
    exit 1
  fi
  if git merge-base --is-ancestor "$ref" HEAD; then
    echo "OK: $ref is an ancestor of HEAD"
  else
    echo "FAIL: $ref is not merged into HEAD (sync with main / merge branches)." >&2
    exit 1
  fi
done

PY=python3
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

echo "Running full test suite..."
"$PY" -m pytest tests/ -q
echo "API track integration checks passed."
