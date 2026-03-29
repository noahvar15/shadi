#!/usr/bin/env bash
# Exit 0 if LORA_ADAPTERS_PATH contains the four expected adapter directories.
# Usage: LORA_ADAPTERS_PATH=/path ./scripts/verify_lora_adapters.sh
# If LORA_ADAPTERS_PATH is unset, reads it from repo .env (same key) when present.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${LORA_ADAPTERS_PATH:-}" && -f "${REPO_ROOT}/.env" ]]; then
  line="$(grep -E '^[[:space:]]*LORA_ADAPTERS_PATH=' "${REPO_ROOT}/.env" 2>/dev/null | tail -n1 || true)"
  if [[ -n "$line" ]]; then
    val="${line#*=}"
    val="${val%\"}"
    val="${val#\"}"
    val="${val%\'}"
    val="${val#\'}"
    LORA_ADAPTERS_PATH="$val"
  fi
fi

ROOT="${LORA_ADAPTERS_PATH:-/models/adapters}"
required=(cardiology neurology pulmonology toxicology)
missing=()

for name in "${required[@]}"; do
  if [[ ! -d "${ROOT}/${name}" ]]; then
    missing+=("${name}")
  fi
done

if ((${#missing[@]})); then
  echo "LORA_ADAPTERS_PATH=${ROOT}"
  if [[ ! -d "$ROOT" ]]; then
    echo "That path is not a directory (yet)."
    echo "Create it, or set LORA_ADAPTERS_PATH in .env to your adapter root."
  fi
  echo "Missing subdirs: ${missing[*]}"
  echo "LoRA checkpoints are not in the git repo."
  echo "Either add cardiology/, neurology/, pulmonology/, toxicology/ under the path above,"
  echo "Optional vLLM LoRA stack: docker compose --profile vllm-lora (see ADR-003); agents use Ollama Meditron (ADR-004)."
  exit 1
fi

echo "OK: all four LoRA adapter directories present under ${ROOT}"
