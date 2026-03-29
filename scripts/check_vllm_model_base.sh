#!/usr/bin/env bash
# Fail fast before `docker compose up vllm` if MODEL_BASE_PATH is not a valid vLLM model dir.
# vLLM error: "Invalid repository ID or local directory specified: '/models/base'"
# means the host mount lacks config.json (HF) or params.json (Mistral).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${MODEL_BASE_PATH:-}" && -f "${REPO_ROOT}/.env" ]]; then
  line="$(grep -E '^[[:space:]]*MODEL_BASE_PATH=' "${REPO_ROOT}/.env" 2>/dev/null | tail -n1 || true)"
  if [[ -n "$line" ]]; then
    val="${line#*=}"
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    MODEL_BASE_PATH="$val"
  fi
fi

ROOT="${MODEL_BASE_PATH:-/models/meditron-70b}"

if [[ ! -d "$ROOT" ]]; then
  echo "MODEL_BASE_PATH=${ROOT} is not a directory."
  echo "Create it and download Meditron (or your base) weights there, or set MODEL_BASE_PATH in .env."
  exit 1
fi

if [[ ! -f "${ROOT}/config.json" && ! -f "${ROOT}/params.json" ]]; then
  echo "MODEL_BASE_PATH=${ROOT} has no config.json (Hugging Face) or params.json (Mistral)."
  echo "vLLM will crash with: Invalid repository ID or local directory specified: '/models/base'"
  exit 1
fi

echo "MODEL_BASE_PATH OK: ${ROOT}"
exit 0
