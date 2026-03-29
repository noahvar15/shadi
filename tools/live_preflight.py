"""Pre-flight checks before ``MOCK_LLM=false`` CLI / local runs.

Validates Postgres TCP reachability and that required Ollama models appear in
``GET /api/tags``. Used by ``tools.shadi_run_case_cli --live``.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse


def _pg_host_port(database_url: str) -> tuple[str, int]:
    raw = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(raw)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    return host, port


def _ollama_api_root(ollama_v1_base: str) -> str:
    return ollama_v1_base.removesuffix("/v1").rstrip("/") or "http://localhost:11434"


def collect_live_preflight_issues() -> tuple[list[str], list[str]]:
    """Return ``(fatal_errors, warnings)`` using :mod:`config`.settings (import lazily)."""
    from config import settings

    errors: list[str] = []
    warnings: list[str] = []

    host, port = _pg_host_port(settings.DATABASE_URL)
    try:
        with socket.create_connection((host, port), timeout=5.0):
            pass
    except OSError as exc:
        errors.append(
            f"Postgres unreachable at {host}:{port} ({exc}). "
            "Start it (e.g. docker compose up -d postgres) or fix DATABASE_URL."
        )

    root = _ollama_api_root(settings.OLLAMA_BASE_URL)
    tags_url = f"{root}/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=10.0) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        errors.append(
            f"Ollama API not usable at {tags_url!r} ({exc}). "
            f"Ensure Ollama is listening (host or docker) and OLLAMA_BASE_URL is correct."
        )
        return errors, warnings

    names = {str(m.get("name", "")).strip() for m in payload.get("models", []) if m.get("name")}

    def _ollama_has_model(required: str) -> bool:
        """Ollama /api/tags uses full tags (e.g. nomic-embed-text:latest); .env often omits :latest."""
        if required in names:
            return True
        p = required + ":"
        return any(n.startswith(p) for n in names)

    required = [
        settings.MEDITRON_MODEL.strip(),
        settings.ORCHESTRATOR_MODEL.strip(),
        settings.SAFETY_MODEL.strip(),
        settings.EVIDENCE_EMBED_MODEL.strip(),
    ]
    for model in required:
        if not model:
            continue
        if not _ollama_has_model(model):
            errors.append(f"Ollama model {model!r} not found in `ollama list`. Run: ollama pull {model}")

    return errors, warnings
