#!/usr/bin/env bash
# Run the pytest subset appropriate for each stacked API branch (issues #31–#34).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

ORIGINAL_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
cleanup() {
  git checkout "$ORIGINAL_BRANCH" 2>/dev/null || true
}
trap cleanup EXIT

PY=python3
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
fi

run_on_branch() {
  local branch="$1"
  shift
  echo "========== $branch =========="
  git checkout "$branch"
  "$PY" -m pytest "$@" -q --tb=line
  echo
}

run_on_branch issue/31-api-lifespan-settings \
  tests/unit/test_api_issue_31.py \
  tests/unit/test_fhir_normalizer.py \
  tests/unit/test_agents.py

run_on_branch issue/32-post-cases-intake \
  tests/unit/test_api_issue_31.py \
  tests/unit/test_api_issue_32.py \
  tests/unit/test_fhir_normalizer.py \
  tests/unit/test_agents.py

run_on_branch issue/33-reports-pipeline-stub \
  tests/unit/test_api_issue_31.py \
  tests/unit/test_api_issue_32.py \
  tests/unit/test_api_issue_33.py \
  tests/unit/test_fhir_normalizer.py \
  tests/unit/test_agents.py

run_on_branch issue/34-arq-worker-and-tests \
  tests/

echo "All branch test subsets passed."
