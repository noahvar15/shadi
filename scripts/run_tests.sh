#!/usr/bin/env bash
# Run pytest with the project venv when present; else fall back to python3 -m pytest.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  exec "$ROOT/.venv/bin/python" -m pytest "$@"
else
  echo "No .venv — create one: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exec python3 -m pytest "$@"
fi
